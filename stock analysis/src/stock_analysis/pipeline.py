from __future__ import annotations

from .config import Settings
from .indicators import calculate_snapshot
from .market_data import build_market_data_provider
from .models import StockAnalysisResult
from .ranking import score_technicals
from .watchlist import load_watchlist


def collect_watchlist_snapshots(settings: Settings) -> tuple[list[StockAnalysisResult], list[str]]:
    watchlist = load_watchlist(settings)
    if not watchlist:
        raise ValueError("Watchlist is empty")

    provider = build_market_data_provider(settings)
    results: list[StockAnalysisResult] = []
    skipped: list[str] = []

    for item in watchlist:
        try:
            history = provider.load_history(item)
            snapshot = calculate_snapshot(history)
            technical_score, technical_summary = score_technicals(snapshot)
            results.append(
                StockAnalysisResult(
                    symbol=item.symbol,
                    name=item.name or item.symbol,
                    technicals=snapshot,
                    technical_score=technical_score,
                    llm_score=technical_score,
                    priority_score=technical_score,
                    recommendation="待Codex分析",
                    reasoning="等待 Codex 按 100 分模板输出正式结论。",
                    extra={"technical_summary": technical_summary},
                )
            )
        except Exception as exc:
            skipped.append(f"{item.symbol}: {exc}")

    if not results:
        raise ValueError("No stocks could be analyzed successfully")

    ranked = sorted(results, key=lambda item: item.priority_score, reverse=True)[: settings.top_k]
    return ranked, skipped
