from __future__ import annotations

from pathlib import Path

from .config import Settings
from .feishu import render_markdown_report, send_ranked_results
from .llm import LlmAnalyzer, RuleBasedAnalyzer
from .models import StockAnalysisResult
from .pipeline import collect_watchlist_snapshots
from .ranking import combine_priority_score


def main() -> int:
    settings = Settings.load()
    base_results, skipped = collect_watchlist_snapshots(settings)
    analyzer = _build_analyzer(settings)

    results: list[StockAnalysisResult] = []
    for item in base_results:
        try:
            llm_score, recommendation, reasoning, llm_extra = analyzer.analyze(
                _to_watchlist_item(item),
                item.technicals,
                str(item.extra.get("technical_summary", "")),
            )
            item.llm_score = llm_score
            item.priority_score = combine_priority_score(item.technical_score, llm_score)
            item.recommendation = recommendation
            item.reasoning = reasoning
            item.extra = {**item.extra, **llm_extra}
            results.append(item)
        except Exception as exc:
            skipped.append(f"{item.symbol}: {exc}")

    if not results:
        raise ValueError("No stocks could be analyzed successfully")

    ranked = sorted(results, key=lambda current: current.priority_score, reverse=True)[: settings.top_k]
    for skipped_item in skipped:
        print(f"Skipping {skipped_item}")
    for index, result in enumerate(ranked, start=1):
        print(
            f"{index}. {result.symbol} {result.name} "
            f"priority={result.priority_score:.1f} "
            f"technical={result.technical_score:.1f} llm={result.llm_score:.1f}"
        )
    _write_report(settings.output_file, render_markdown_report(ranked))
    if settings.send_feishu:
        send_ranked_results(settings, ranked)
    return 0


def _build_analyzer(settings: Settings) -> LlmAnalyzer | RuleBasedAnalyzer:
    if settings.enable_llm and settings.openai_api_key:
        return LlmAnalyzer(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    return RuleBasedAnalyzer()


def _to_watchlist_item(result: StockAnalysisResult):
    from .models import WatchlistItem

    return WatchlistItem(symbol=result.symbol, name=result.name)


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
