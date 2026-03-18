from __future__ import annotations

import math

from .models import PriceBar, TechnicalSnapshot


def calculate_snapshot(bars: list[PriceBar]) -> TechnicalSnapshot:
    closes = [bar.close for bar in bars]
    latest_close = closes[-1]
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    rsi14 = _rsi(closes, 14)
    macd, macd_signal, macd_hist = _macd(closes)
    momentum_20d = ((latest_close / closes[-21]) - 1) * 100
    volatility_20d = _annualized_volatility(closes[-20:])
    return TechnicalSnapshot(
        latest_close=latest_close,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        rsi14=rsi14,
        macd=macd,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        momentum_20d=momentum_20d,
        volatility_20d=volatility_20d,
    )


def _sma(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def _ema(values: list[float], window: int) -> float:
    multiplier = 2 / (window + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _ema_series(values: list[float], window: int) -> list[float]:
    multiplier = 2 / (window + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def _rsi(values: list[float], window: int) -> float:
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[:-1], values[1:]):
        diff = current - previous
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window
    for gain, loss in zip(gains[window:], losses[window:]):
        avg_gain = ((avg_gain * (window - 1)) + gain) / window
        avg_loss = ((avg_loss * (window - 1)) + loss) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(values: list[float]) -> tuple[float, float, float]:
    ema12 = _ema_series(values, 12)
    ema26 = _ema_series(values, 26)
    diffs = [short - long for short, long in zip(ema12, ema26)]
    signal_series = _ema_series(diffs, 9)
    macd = diffs[-1]
    signal = signal_series[-1]
    hist = macd - signal
    return macd, signal, hist


def _annualized_volatility(values: list[float]) -> float:
    returns = []
    for previous, current in zip(values[:-1], values[1:]):
        returns.append((current / previous) - 1)
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return math.sqrt(variance) * math.sqrt(252) * 100

