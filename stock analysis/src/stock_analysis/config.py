from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(slots=True)
class Settings:
    openai_api_key: str
    openai_model: str
    feishu_webhook_url: str
    feishu_send_mode: str
    feishu_app_id: str
    feishu_app_secret: str
    feishu_receive_id_type: str
    feishu_receive_id: str
    watchlist_source: str
    watchlist_file: Path
    market_data_source: str
    history_dir: Path
    manual_symbols: list[str]
    clipboard_encoding: str
    broker_window_title: str
    watchlist_tab_text: str
    watchlist_copy_shortcut: list[str]
    broker_data_dir: Path | None
    broker_watchlist_patterns: list[str]
    analysis_days: int
    top_k: int
    enable_llm: bool
    send_feishu: bool
    output_file: Path

    @classmethod
    def load(cls, cwd: Path | None = None) -> "Settings":
        base_dir = cwd or Path.cwd()
        _load_dotenv(base_dir / ".env")
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", ""),
            feishu_send_mode=os.getenv("FEISHU_SEND_MODE", "app").lower(),
            feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
            feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            feishu_receive_id_type=os.getenv("FEISHU_RECEIVE_ID_TYPE", "open_id").lower(),
            feishu_receive_id=os.getenv("FEISHU_RECEIVE_ID", ""),
            watchlist_source=os.getenv("WATCHLIST_SOURCE", "csv").lower(),
            watchlist_file=base_dir / os.getenv("WATCHLIST_FILE", "data/watchlist.csv"),
            market_data_source=os.getenv("MARKET_DATA_SOURCE", "eastmoney").lower(),
            history_dir=base_dir / os.getenv("HISTORY_DIR", "data/history"),
            manual_symbols=[
                item.strip()
                for item in os.getenv("MANUAL_SYMBOLS", "").split(",")
                if item.strip()
            ],
            clipboard_encoding=os.getenv("CLIPBOARD_ENCODING", "auto").lower(),
            broker_window_title=os.getenv("BROKER_WINDOW_TITLE", "招商证券"),
            watchlist_tab_text=os.getenv("WATCHLIST_TAB_TEXT", "自选"),
            watchlist_copy_shortcut=[
                item.strip()
                for item in os.getenv("WATCHLIST_COPY_SHORTCUT", "^a,^c").split(",")
                if item.strip()
            ],
            broker_data_dir=(
                base_dir / os.getenv("BROKER_DATA_DIR")
                if os.getenv("BROKER_DATA_DIR", "").strip()
                else None
            ),
            broker_watchlist_patterns=[
                item.strip()
                for item in os.getenv(
                    "BROKER_WATCHLIST_PATTERNS",
                    "*.blk,*.ebk,*.txt,*.csv,*.ini,*.dat",
                ).split(",")
                if item.strip()
            ],
            analysis_days=int(os.getenv("ANALYSIS_DAYS", "180")),
            top_k=int(os.getenv("TOP_K", "10")),
            enable_llm=os.getenv("ENABLE_LLM", "true").lower() in {"1", "true", "yes", "on"},
            send_feishu=os.getenv("SEND_FEISHU", "true").lower() in {"1", "true", "yes", "on"},
            output_file=base_dir / os.getenv("OUTPUT_FILE", "output/latest_report.md"),
        )
