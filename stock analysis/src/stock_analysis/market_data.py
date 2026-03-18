from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from curl_cffi import requests

from .config import Settings
from .models import PriceBar, WatchlistItem


@dataclass(slots=True)
class EastmoneyMarketDataProvider:
    history_days: int = 180

    def load_history(self, item: WatchlistItem) -> list[PriceBar]:
        end = datetime.now()
        start = end - timedelta(days=max(self.history_days * 2, 240))
        response = requests.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
                "klt": "101",
                "fqt": "1",
                "secid": _secid(item.symbol),
                "beg": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
            },
            impersonate="chrome110",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not data:
            raise ValueError(f"No market data returned for symbol: {item.symbol}")
        if not item.name or item.name == item.symbol:
            item.name = str(data.get("name") or item.symbol).strip() or item.symbol
        klines = data.get("klines", [])
        bars: list[PriceBar] = []
        for raw in klines[-self.history_days :]:
            date, open_price, close, high, low, volume, *_ = raw.split(",")
            bars.append(
                PriceBar(
                    date=date,
                    open=float(open_price),
                    close=float(close),
                    high=float(high),
                    low=float(low),
                    volume=float(volume),
                )
            )
        if len(bars) < 60:
            raise ValueError(f"{item.symbol} historical data is insufficient; expected at least 60 bars")
        return bars


@dataclass(slots=True)
class CsvMarketDataProvider:
    history_dir: Path

    def load_history(self, item: WatchlistItem) -> list[PriceBar]:
        file_path = self.history_dir / f"{item.symbol}.csv"
        with file_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            bars = [
                PriceBar(
                    date=str(row["date"]),
                    open=float(row["open"]),
                    close=float(row["close"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    volume=float(row["volume"]),
                )
                for row in reader
            ]
        if len(bars) < 60:
            raise ValueError(f"{file_path} historical data is insufficient; expected at least 60 rows")
        return bars


def build_market_data_provider(settings: Settings) -> EastmoneyMarketDataProvider | CsvMarketDataProvider:
    if settings.market_data_source == "eastmoney":
        return EastmoneyMarketDataProvider(history_days=settings.analysis_days)
    if settings.market_data_source == "csv":
        return CsvMarketDataProvider(history_dir=settings.history_dir)
    raise ValueError(f"Unsupported market data source: {settings.market_data_source}")


def _secid(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9", "11", "13")):
        return f"1.{symbol}"
    return f"0.{symbol}"
