from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WatchlistItem:
    symbol: str
    name: str | None = None


@dataclass(slots=True)
class PriceBar:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float


@dataclass(slots=True)
class TechnicalSnapshot:
    latest_close: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    rsi14: float
    macd: float
    macd_signal: float
    macd_hist: float
    momentum_20d: float
    volatility_20d: float


@dataclass(slots=True)
class StockAnalysisResult:
    symbol: str
    name: str
    technicals: TechnicalSnapshot
    technical_score: float
    llm_score: float
    priority_score: float
    recommendation: str
    reasoning: str
    extra: dict[str, Any] = field(default_factory=dict)
