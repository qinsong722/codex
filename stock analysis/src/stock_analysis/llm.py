from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .models import TechnicalSnapshot, WatchlistItem


class LlmAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def analyze(
        self,
        item: WatchlistItem,
        snapshot: TechnicalSnapshot,
        technical_summary: str,
    ) -> tuple[float, str, str, dict[str, Any]]:
        prompt = f"""
你是专业的A股股票评分分析助手。请严格按以下100分制股票评分模型，对指定股票输出结构化结论。

评分框架：
总分 = 行业景气度（20） + 公司竞争力（25） + 财务质量（20） + 估值水平（20） + 周期与资金位置（15） - 红旗扣分（0到15）

评级标准：
- 90-100：顶级标的
- 80-89：优质标的
- 70-79：可配置标的
- 60-69：一般标的
- 60以下：回避标的

要求：
1. 必须给出明确判断，不能模棱两可
2. 必须回答“好不好、贵不贵、值不值得配置、当前是不是好时点”
3. 红旗风险必须单列
4. 如果缺少部分基本面资料，可以结合行业常识和当前技术面做“谨慎推断”，但要保持结论鲜明
5. 输出必须是合法JSON，不要输出JSON以外的任何文字

请输出如下 JSON 结构：
{{
  "score": 0-100,
  "rating": "顶级标的|优质标的|可配置标的|一般标的|回避标的",
  "recommendation": "可以配置|可以小仓跟踪|不适合追高|等回调再看|暂不建议参与",
  "one_line_conclusion": "一句话结论",
  "reasoning": "不超过140字的总体判断",
  "breakdown": {{
    "industry_prosperity": {{"score": 0-20, "reason": "..." }},
    "company_competitiveness": {{"score": 0-25, "reason": "..." }},
    "financial_quality": {{"score": 0-20, "reason": "..." }},
    "valuation_level": {{"score": 0-20, "reason": "..." }},
    "cycle_and_flow": {{"score": 0-15, "reason": "..." }},
    "red_flag_penalty": {{"score": 0-15, "reason": "没有明显问题则写无明显红旗" }}
  }},
  "strengths": ["优点1", "优点2", "优点3"],
  "risks": ["风险1", "风险2", "风险3"],
  "follow_up_metrics": ["指标1", "指标2", "指标3"],
  "detailed_analysis": {{
    "industry_prosperity": "...",
    "company_competitiveness": "...",
    "financial_quality": "...",
    "valuation_level": "...",
    "cycle_and_flow": "...",
    "red_flag_penalty": "..."
  }}
}}

股票代码：{item.symbol}
公司名称：{item.name or item.symbol}
最新收盘价：{snapshot.latest_close:.2f}
MA5/10/20/60：{snapshot.ma5:.2f}/{snapshot.ma10:.2f}/{snapshot.ma20:.2f}/{snapshot.ma60:.2f}
RSI14：{snapshot.rsi14:.2f}
MACD：{snapshot.macd:.3f}
MACD_SIGNAL：{snapshot.macd_signal:.3f}
MACD_HIST：{snapshot.macd_hist:.3f}
20日动量：{snapshot.momentum_20d:.2f}%
20日波动率：{snapshot.volatility_20d:.2f}%
技术面总结：{technical_summary}
"""
        response = self._client.responses.create(model=self._model, input=prompt)
        text = response.output_text.strip()
        data = json.loads(_extract_json(text))
        score = max(0.0, min(100.0, float(data.get("score", 50))))
        recommendation = str(data.get("recommendation", "等回调再看")).strip()
        reasoning = str(data.get("reasoning", "")).strip()
        extra = {
            "rating": str(data.get("rating", _rating_from_score(score))).strip(),
            "one_line_conclusion": str(data.get("one_line_conclusion", reasoning)).strip(),
            "strengths": _normalize_list(data.get("strengths")),
            "risks": _normalize_list(data.get("risks")),
            "follow_up_metrics": _normalize_list(data.get("follow_up_metrics")),
            "breakdown": data.get("breakdown", {}),
            "detailed_analysis": data.get("detailed_analysis", {}),
        }
        return score, recommendation, reasoning, extra


class RuleBasedAnalyzer:
    def analyze(
        self,
        item: WatchlistItem,
        snapshot: TechnicalSnapshot,
        technical_summary: str,
    ) -> tuple[float, str, str, dict[str, Any]]:
        technical_component = 0.0
        if snapshot.ma5 > snapshot.ma20:
            technical_component += 4
        if snapshot.ma20 > snapshot.ma60:
            technical_component += 4
        if snapshot.macd_hist > 0:
            technical_component += 4
        if 45 <= snapshot.rsi14 <= 70:
            technical_component += 4
        if snapshot.momentum_20d > 0:
            technical_component += 4

        industry = 10.0
        company = 13.0
        financial = 12.0
        valuation = 11.0
        cycle = min(15.0, 7.0 + technical_component)
        red_flag_penalty = 0.0
        score = max(0.0, min(100.0, industry + company + financial + valuation + cycle - red_flag_penalty))

        if score >= 90:
            rating = "顶级标的"
            recommendation = "可以配置"
        elif score >= 80:
            rating = "优质标的"
            recommendation = "可以配置"
        elif score >= 70:
            rating = "可配置标的"
            recommendation = "可以小仓跟踪"
        elif score >= 60:
            rating = "一般标的"
            recommendation = "等回调再看"
        else:
            rating = "回避标的"
            recommendation = "暂不建议参与"

        reasoning = f"{item.symbol} 当前使用规则评分，技术面特征为：{technical_summary}。"
        extra = {
            "rating": rating,
            "one_line_conclusion": f"{item.name or item.symbol} 当前更适合按技术面强弱决定仓位与节奏。",
            "strengths": _normalize_list([technical_summary, "走势信号已纳入评分", "可用于自选股优先级排序"]),
            "risks": _normalize_list(["规则模型未纳入完整基本面", "短期波动可能放大", "需要结合后续公告验证"]),
            "follow_up_metrics": _normalize_list(["MA20与MA60关系", "MACD柱体变化", "20日动量", "成交量变化"]),
            "breakdown": {
                "industry_prosperity": {"score": industry, "reason": "规则模式下使用中性行业评分。"},
                "company_competitiveness": {"score": company, "reason": "规则模式下使用中性公司质量评分。"},
                "financial_quality": {"score": financial, "reason": "规则模式下使用中性财务评分。"},
                "valuation_level": {"score": valuation, "reason": "规则模式下未接入历史估值分位，给予中性分。"},
                "cycle_and_flow": {"score": cycle, "reason": f"根据技术面给分：{technical_summary}。"},
                "red_flag_penalty": {"score": red_flag_penalty, "reason": "规则模式下未发现明确红旗扣分项。"},
            },
            "detailed_analysis": {
                "industry_prosperity": "规则模式未接入行业数据库，行业评分保守处理中性。",
                "company_competitiveness": "规则模式未接入公司治理和市场份额数据，公司竞争力按中性估计。",
                "financial_quality": "规则模式未接入财报明细，财务质量按中性估计。",
                "valuation_level": "规则模式未接入PE/PB历史分位，因此不对低估或高估做强判断。",
                "cycle_and_flow": f"当前周期与交易位置主要依据技术面，结论为：{technical_summary}。",
                "red_flag_penalty": "未发现明确的红旗事项，但规则模式不等同于完整尽调。",
            },
        }
        return score, recommendation, reasoning, extra


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"LLM did not return valid JSON: {text}")
    return text[start : end + 1]


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _rating_from_score(score: float) -> str:
    if score >= 90:
        return "顶级标的"
    if score >= 80:
        return "优质标的"
    if score >= 70:
        return "可配置标的"
    if score >= 60:
        return "一般标的"
    return "回避标的"
