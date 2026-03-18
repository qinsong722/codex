from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .pipeline import collect_watchlist_snapshots


def main() -> int:
    settings = Settings.load()
    results, skipped = collect_watchlist_snapshots(settings)
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompt_version": "codex-stock-score-v1",
        "instructions": (
            "请按约定的100分制股票评分模板，对列表中的股票逐只输出结构化分析；"
            "必须给出综合评分、评级、一句话结论、详细分析、核心优点、核心风险、跟踪指标和操作建议。"
        ),
        "stocks": [
            {
                "symbol": result.symbol,
                "name": result.name,
                "technical_score": result.technical_score,
                "technical_summary": result.extra.get("technical_summary", ""),
                "snapshot": {
                    "latest_close": result.technicals.latest_close,
                    "ma5": result.technicals.ma5,
                    "ma10": result.technicals.ma10,
                    "ma20": result.technicals.ma20,
                    "ma60": result.technicals.ma60,
                    "rsi14": result.technicals.rsi14,
                    "macd": result.technicals.macd,
                    "macd_signal": result.technicals.macd_signal,
                    "macd_hist": result.technicals.macd_hist,
                    "momentum_20d": result.technicals.momentum_20d,
                    "volatility_20d": result.technicals.volatility_20d,
                },
            }
            for result in results
        ],
        "skipped": skipped,
    }
    json_path = output_dir / "codex_analysis_input.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    prompt_path = output_dir / "codex_analysis_prompt.md"
    prompt_path.write_text(_build_prompt_text(json_path), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {prompt_path}")
    return 0


def _build_prompt_text(json_path: Path) -> str:
    return (
        "在 Codex 中运行以下任务：\n\n"
        f"1. 读取 `{json_path}`\n"
        "2. 按 100 分制股票评分模板逐只分析 `stocks` 中的股票\n"
        "3. 生成一份 Markdown 报告到 `output/codex_scored_report.md`\n"
        "4. 报告中先给出按综合评分排序的结果，再给出每只股票的详细分析\n"
        "5. 如果需要发送飞书，再把报告摘要整理成文本消息\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
