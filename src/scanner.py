"""
scanner.py - detect Donchian 20/10 breakout signals on the watchlist.

A "signal" is a NEW event for a ticker - either:
  - ENTRY  : today's close > 20-day high (new breakout -> buy signal)
  - EXIT   : today's close < 10-day low  (exit signal if you hold the name)

The scanner keeps a small state file (results/scan_state.json) so each signal
fires only once. Re-running the same day won't produce duplicate alerts.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import config


@dataclass
class Signal:
    ticker: str
    type: str           # "ENTRY" or "EXIT"
    date: str           # YYYY-MM-DD
    close: float
    level: float        # breakout level (20-day high) or breakdown level (10-day low)
    atr_pct: Optional[float] = None  # ATR/price in %, useful for sizing
    prior_high: Optional[float] = None  # the 20d high we broke (entries)
    prior_low: Optional[float] = None   # the 10d low we broke (exits)


def _load_state() -> Dict:
    if not os.path.exists(config.STATE_FILE):
        return {}
    try:
        with open(config.STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: Dict) -> None:
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _atr(close: pd.Series, window: int = 20) -> float:
    """Close-to-close ATR proxy as fraction of price (last value)."""
    tr = (close - close.shift(1)).abs()
    a = tr.rolling(window).mean()
    val = a.iloc[-1] if len(a) else np.nan
    if not np.isfinite(val) or close.iloc[-1] <= 0:
        return np.nan
    return float(val / close.iloc[-1])  # decimal


def scan_ticker(df: pd.DataFrame, ticker: str) -> List[Signal]:
    """
    Inspect the LAST bar of df for a Donchian entry or exit signal.
    Returns [] if no new signal, or [Signal(...)] for a fresh setup.
    """
    if df is None or len(df) < max(config.ENTRY_WINDOW, config.EXIT_WINDOW) + 2:
        return []

    close = df["Close"].astype(float)
    # Use High/Low if we have them, else fall back to Close
    high = df["High"].astype(float) if "High" in df.columns else close
    low  = df["Low"].astype(float)  if "Low"  in df.columns else close

    # The most recent *closed* bar is index -1. We compute reference levels using
    # bars *strictly before* it (no look-ahead).
    i = len(df) - 1
    entry_window_high = high.iloc[i - config.ENTRY_WINDOW - 1 : i - 1 + 1].max()
    # 20-day high of bars [i-20, i-1]; we want today to break it
    # Actually correct Donchian: "today's close > max(high last 20 days excluding today)"
    entry_ref = high.iloc[i - config.ENTRY_WINDOW : i].max()  # last 20 days incl today-1
    exit_ref  = low.iloc[i - config.EXIT_WINDOW  : i].min()   # last 10 days incl today-1
    today_close = float(close.iloc[i])
    today_high  = float(high.iloc[i])
    today_low   = float(low.iloc[i])
    today_date  = df.index[i].strftime("%Y-%m-%d")

    atr_pct = _atr(close, config.ATR_WINDOW)

    signals: List[Signal] = []

    # ENTRY: today broke to a new 20-day high
    if today_high > entry_ref and today_close >= entry_ref:
        signals.append(Signal(
            ticker=ticker,
            type="ENTRY",
            date=today_date,
            close=round(today_close, 2),
            level=round(float(entry_ref), 2),
            atr_pct=round(atr_pct * 100, 2) if np.isfinite(atr_pct) else None,
            prior_high=round(float(entry_ref), 2),
        ))

    # EXIT: today broke the 10-day low (used only if user currently holds the name)
    if today_low < exit_ref and today_close <= exit_ref:
        signals.append(Signal(
            ticker=ticker,
            type="EXIT",
            date=today_date,
            close=round(today_close, 2),
            level=round(float(exit_ref), 2),
            atr_pct=round(atr_pct * 100, 2) if np.isfinite(atr_pct) else None,
            prior_low=round(float(exit_ref), 2),
        ))

    return signals


def scan_watchlist(df_dict: Dict[str, pd.DataFrame],
                   state: Optional[Dict] = None) -> Dict[str, List[Signal]]:
    """
    Run scan on every ticker; filter out signals already fired (state file).
    Returns dict: ticker -> list of NEW signals today (length 0, 1, or 2).
    """
    if state is None:
        state = _load_state()

    new_state = dict(state)
    out: Dict[str, List[Signal]] = {}

    for ticker, df in df_dict.items():
        sigs = scan_ticker(df, ticker)
        # Filter out already-fired (same ticker + same type + same date)
        fresh = []
        for s in sigs:
            key = f"{ticker}_{s.type}_{s.date}"
            if key in state:
                continue
            fresh.append(s)
            new_state[key] = True
        if fresh:
            out[ticker] = fresh

    _save_state(new_state)
    return out


def signal_summary_text(signals: Dict[str, List[Signal]]) -> str:
    """Plain-text summary suitable for a chat message."""
    if not signals:
        return "Donchian 20/10 scan: no new signals today."
    lines = [f"📊 DONCHIAN 20/10 SCAN — {sum(len(v) for v in signals.values())} new signal(s)"]
    for ticker, sigs in signals.items():
        for s in sigs:
            if s.type == "ENTRY":
                lines.append(
                    f"\n🟢 ENTRY  {ticker}  ({s.date})\n"
                    f"  Close ${s.close}  vs 20d high ${s.level}\n"
                    f"  Stop exit if close < 10d low\n"
                    f"  ATR~{s.atr_pct}% of price (size ≈ {1.0/(s.atr_pct/100) if s.atr_pct else '?'}% of equity per 1% risk)"
                )
            else:
                lines.append(
                    f"\n🔴 EXIT   {ticker}  ({s.date})\n"
                    f"  Close ${s.close}  broke 10d low ${s.level}"
                )
    return "\n".join(lines)


if __name__ == "__main__":
    # Smoke test: scan all watchlist tickers with cached data
    import data
    print("Fetching watchlist ...")
    df_dict = data.fetch_universe(
        start="2024-01-01",
        end="2025-12-31",
        tickers=config.WATCHLIST,
    )
    print(f"Got data for {len(df_dict)} tickers\n")
    state = _load_state()
    signals = scan_watchlist(df_dict, state=state)
    print(signal_summary_text(signals))
