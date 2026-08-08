"""
data.py - fetch US+CA ETF price history via yfinance, with local parquet cache.

Universe: a fixed list of liquid US and Canadian ETFs covering equity, bond,
sector, gold, oil, REIT, currency - enough to run all six survivor strategies.

Cache: each ticker is saved as data/<TICKER>.parquet. We refresh only if older
than DATA_TTL_HOURS or if the local file is missing.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd
import yfinance as yf

# ------------------------------------------------------------------
# Universe (US + CA ETFs)
# ------------------------------------------------------------------
# Naming: yfinance expects ".TO" suffix for Toronto Stock Exchange tickers.
UNIVERSE = {
    # US broad equity / sector
    "SPY":  "US large-cap equity (S&P 500)",
    "QQQ":  "US Nasdaq-100",
    "IWM":  "US small-cap (Russell 2000)",
    "DIA":  "US Dow 30",
    "XLK":  "US Tech sector",
    "XLF":  "US Financials",
    "XLE":  "US Energy",
    "XLV":  "US Health Care",
    "XLI":  "US Industrials",
    "VNQ":  "US REITs",
    # US other assets
    "AGG":  "US aggregate bonds",
    "GLD":  "Gold",
    "USO":  "WTI crude oil",
    "DBC":  "Broad commodities",
    "BIL":  "US 1-3M T-bill (cash proxy)",
    # Canada
    "XIC.TO": "TSX Capped Composite (CA large-cap)",
    "XSP.TO": "S&P 500 CAD-hedged",
    "XBB.TO": "CA gov bonds",
    "XEF.TO": "CA iShares developed intl (CAD-hedged)",
    "FXC":   "CAD/USD (currency hedge proxy)",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_TTL_HOURS = 24


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace(".", "_")
    return DATA_DIR / f"{safe}.csv"


def _needs_refresh(path: Path) -> bool:
    if not path.exists():
        return True
    age_h = (time.time() - path.stat().st_mtime) / 3600.0
    return age_h > DATA_TTL_HOURS


def fetch_ticker(ticker: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """Download (or load cached) daily OHLCV for one ticker as a clean DataFrame."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(ticker)
    if not force and not _needs_refresh(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df.loc[start:end]

    df = yf.download(ticker, start=start, end=end, progress=False,
                     auto_adjust=True, multi_level_index=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data returned for {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    # Keep standard columns
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()
    df.to_csv(path)
    return df


def fetch_universe(start: str, end: str,
                   tickers: Optional[Iterable[str]] = None,
                   force: bool = False,
                   quiet: bool = False,
                   min_bars: int = 252) -> Dict[str, pd.DataFrame]:
    """Fetch daily data for the universe (or subset). Returns dict ticker -> df."""
    tickers = list(tickers) if tickers else list(UNIVERSE.keys())
    out: Dict[str, pd.DataFrame] = {}
    for i, t in enumerate(tickers, start=1):
        try:
            df = fetch_ticker(t, start=start, end=end, force=force)
            if len(df) < min_bars:
                if not quiet:
                    print(f"  [{i:>2}/{len(tickers)}] {t:<7} only {len(df)} bars - skipped")
                continue
            out[t] = df
            if not quiet:
                print(f"  [{i:>2}/{len(tickers)}] {t:<7} {len(df):>5} bars "
                      f"({df.index[0].date()} -> {df.index[-1].date()})")
        except Exception as e:
            if not quiet:
                print(f"  [{i:>2}/{len(tickers)}] {t:<7} ERROR: {e}")
        # small polite delay
        time.sleep(0.15)
    return out


def aligned_panel(df_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build a single panel of Close prices (one column per ticker), aligned by date."""
    closes = pd.DataFrame({t: d["Close"] for t, d in df_dict.items()})
    closes = closes.dropna(how="all")
    # Forward-fill up to 5 days for stale Canadian holidays (careful: only for close)
    closes = closes.ffill(limit=5)
    return closes


if __name__ == "__main__":
    # Quick sanity check
    d = fetch_universe(start="2015-01-01", end="2024-12-31")
    print(f"\nFetched {len(d)} tickers")
    p = aligned_panel(d)
    print(p.tail())
