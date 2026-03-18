from __future__ import annotations

from .models import TechnicalSnapshot


def score_technicals(snapshot: TechnicalSnapshot) -> tuple[float, str]:
    score = 50.0
    tags: list[str] = []

    if snapshot.ma5 > snapshot.ma20 > snapshot.ma60:
        score += 18
        tags.append("短中长期均线多头")
    elif snapshot.ma5 < snapshot.ma20 < snapshot.ma60:
        score -= 18
        tags.append("均线空头排列")

    if snapshot.macd_hist > 0:
        score += 12
        tags.append("MACD 红柱")
    else:
        score -= 10
        tags.append("MACD 走弱")

    if 45 <= snapshot.rsi14 <= 65:
        score += 10
        tags.append("RSI 健康")
    elif snapshot.rsi14 > 75:
        score -= 8
        tags.append("短线偏热")
    elif snapshot.rsi14 < 30:
        score += 4
        tags.append("可能超跌反弹")

    if snapshot.momentum_20d > 8:
        score += 14
        tags.append("20日动量强")
    elif snapshot.momentum_20d < -8:
        score -= 14
        tags.append("20日动量弱")

    if snapshot.volatility_20d > 45:
        score -= 6
        tags.append("波动偏大")

    bounded = max(0.0, min(100.0, score))
    return bounded, "，".join(tags) or "技术面中性"


def combine_priority_score(technical_score: float, llm_score: float) -> float:
    return round(technical_score * 0.55 + llm_score * 0.45, 2)

