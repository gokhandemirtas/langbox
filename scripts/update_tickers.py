"""Fetch well-known stock tickers from Wikipedia and merge into fixtures/tickers.json.

Sources:
  - S&P 500  (US large-cap, ~500 companies)
  - FTSE 100 (UK large-cap, ~100 companies)

Usage:
    uv run python scripts/update_tickers.py
"""

import io
import json
from pathlib import Path

import pandas as pd
import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; langbox-ticker-updater/1.0)"}

TICKERS_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "tickers.json"

SOURCES = [
    {
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "table_index": 0,
        "symbol_col": "Symbol",
        "name_col": "Security",
        "exchange": "NYSE/NASDAQ",
    },
    {
        "url": "https://en.wikipedia.org/wiki/FTSE_100_Index",
        "table_index": 6,
        "symbol_col": "Ticker",
        "name_col": "Company",
        "exchange": "LSE",
    },
]


def _fetch(source: dict) -> list[dict]:
    print(f"Fetching {source['url']} ...")
    html = requests.get(source["url"], headers=_HEADERS, timeout=15).text
    tables = pd.read_html(io.StringIO(html))
    df = tables[source["table_index"]]

    results = []
    for _, row in df.iterrows():
        ticker = str(row.get(source["symbol_col"], "")).strip()
        name = str(row.get(source["name_col"], "")).strip()
        if ticker and name and ticker != "nan":
            results.append({
                "name": name,
                "ticker": ticker.replace(".", "-"),  # yfinance uses BRK-B not BRK.B
                "exchange": source["exchange"],
            })
    return results


def main():
    # Load existing entries
    existing = json.loads(TICKERS_PATH.read_text()) if TICKERS_PATH.exists() else []
    seen = {e["ticker"].upper() for e in existing}
    merged = list(existing)

    for source in SOURCES:
        try:
            entries = _fetch(source)
            added = 0
            for entry in entries:
                if entry["ticker"].upper() not in seen:
                    merged.append(entry)
                    seen.add(entry["ticker"].upper())
                    added += 1
            print(f"  Added {added} new tickers from {source['exchange']}")
        except Exception as e:
            print(f"  Failed to fetch {source['url']}: {e}")

    merged.sort(key=lambda x: x["name"])
    TICKERS_PATH.write_text(json.dumps(merged, indent=4))
    print(f"\nDone. {len(merged)} total tickers in {TICKERS_PATH}")


if __name__ == "__main__":
    main()
