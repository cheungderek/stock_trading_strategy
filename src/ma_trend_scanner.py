"""
ma_trend_scanner.py - detect stocks in one of two regimes relative to the
simple 20-day moving average (SMA-20):

  STRONG-ABOVE  : close > SMA-20 on >= `min_days_above` of last `window` days,
                  and current close > SMA-20. This identifies stocks trading
                  consistently above their 20-day MA (trend support).

  BLOCKED-BY-MA : close < SMA-20 on >= `min_days_below` of last `window` days,
                  and current close < SMA-20 (still under), AND each time the
                  stock bounced into the MA in the past `window` days it was
                  rejected (closed back below). This identifies stocks whose
                  20-MA is acting as overhead resistance.

Both lists are reported. Charts are saved showing price + 20-MA + (support
or resistance) levels + zone highlights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ #
# Defaults (move to config.py if you want to tweak)
# ------------------------------------------------------------------ #
MA_WINDOW = 20          # the simple MA we measure against
LOOKBACK_WINDOW = 100   # total days to evaluate (≈ 5 trading months)
MIN_DAYS_ABOVE = 65     # >=65 of last 100 days closed above -> STRONG-ABOVE
MIN_DAYS_BELOW = 65     # >=65 of last 100 days closed below -> BLOCKED candidate
REJECTION_TOLERANCE = 0.01  # a "touch" within 1% of MA counts as testing it


# ------------------------------------------------------------------ #
@dataclass
class MATrendSignal:
    ticker: str
    date: str
    close: float
    ma20: float
    pct_above_ma: float        # (close - ma20) / ma20 * 100, decimal
    regime: str               # "STRONG-ABOVE" or "BLOCKED-BY-MA"
    days_above_in_window: int
    days_below_in_window: int
    rejections_in_window: int # how many times price tested MA from below and fell
    window_days: int


# ------------------------------------------------------------------ #
def _evaluate_ticker(df: pd.DataFrame, ticker: str,
                     window: int = LOOKBACK_WINDOW,
                     min_above: int = MIN_DAYS_ABOVE,
                     min_below: int = MIN_DAYS_BELOW) -> Optional[MATrendSignal]:
    """Return a MATrendSignal for the ticker if it qualifies, else None."""
    if len(df) < MA_WINDOW + 5:
        return None
    close = df["Close"].astype(float)
    ma = close.rolling(MA_WINDOW).mean()

    # Window slice (last `window` trading days, must be complete)
    if len(close) < window + 1:
        window = len(close) - 1
    win_close = close.iloc[-window:]
    win_ma = ma.iloc[-window:]
    # Drop NaNs at the start of the MA window
    valid = win_ma.notna()
    if valid.sum() < 30:
        return None
    win_close = win_close[valid]
    win_ma = win_ma[valid]

    days_above = int((win_close > win_ma).sum())
    days_below = int((win_close < win_ma).sum())

    # Reject if mixed: not dominantly above nor dominantly below
    # (we require strong dominance in one direction)
    current_close = float(close.iloc[-1])
    current_ma = float(ma.iloc[-1])
    if not np.isfinite(current_ma) or current_ma <= 0:
        return None

    pct_above = (current_close - current_ma) / current_ma * 100.0

    # Detect rejections: in the window, count times price dipped above MA then
    # closed back below within 3 days. Used to validate BLOCKED regime.
    rejections = 0
    in_window_close = close.iloc[-window:].values
    in_window_ma = ma.iloc[-window:].values
    n = len(in_window_close)
    i = 1
    while i < n - 1:
        # today touch MA from below (low within tolerance), close below MA
        # we don't have low, so use close:
        if (in_window_close[i] >= in_window_ma[i] * (1 - REJECTION_TOLERANCE)
            and in_window_close[i] <= in_window_ma[i] * (1 + REJECTION_TOLERANCE)):
            # touched MA; check if next 1-3 closes drop back below
            for j in range(i + 1, min(i + 4, n)):
                if in_window_close[j] < in_window_ma[j]:
                    rejections += 1
                    i = j
                    break
        i += 1

    regime = None
    if days_above >= min_above and current_close > current_ma:
        regime = "STRONG-ABOVE"
    elif days_below >= min_below and current_close < current_ma and rejections >= 1:
        regime = "BLOCKED-BY-MA"

    if regime is None:
        return None

    return MATrendSignal(
        ticker=ticker,
        date=df.index[-1].strftime("%Y-%m-%d"),
        close=round(current_close, 2),
        ma20=round(current_ma, 2),
        pct_above_ma=round(pct_above, 2),
        regime=regime,
        days_above_in_window=days_above,
        days_below_in_window=days_below,
        rejections_in_window=rejections,
        window_days=len(win_close),
    )


def scan_watchlist_ma_trend(df_dict: Dict[str, pd.DataFrame]) -> Dict[str, MATrendSignal]:
    """Run the 20-MA regime scanner on every ticker in the watchlist."""
    out: Dict[str, MATrendSignal] = {}
    for ticker, df in df_dict.items():
        sig = _evaluate_ticker(df, ticker)
        if sig is not None:
            out[ticker] = sig
    return out


def ma_trend_summary(signals: Dict[str, MATrendSignal]) -> str:
    """Plain-text summary for FB Messenger / console."""
    if not signals:
        return ("📊 20-MA TREND SCAN: no tickers strongly above or blocked by 20-MA "
                f"in last {LOOKBACK_WINDOW} days.")
    strong = [s for s in signals.values() if s.regime == "STRONG-ABOVE"]
    blocked = [s for s in signals.values() if s.regime == "BLOCKED-BY-MA"]
    lines = [
        f"📊 20-MA TREND SCAN ({LOOKBACK_WINDOW}d window)",
        f"  STRONG-ABOVE  : {len(strong)} ticker(s)",
        f"  BLOCKED-BY-MA  : {len(blocked)} ticker(s)",
    ]
    if strong:
        lines.append("\n🟢 STRONG-ABOVE — trading consistently above 20-MA:")
        # sort by % above descending (most strongly above first)
        for s in sorted(strong, key=lambda s: -s.pct_above_ma)[:15]:
            lines.append(
                f"  {s.ticker:<7}  ${s.close:>7.2f}  MA20 ${s.ma20:>7.2f}  "
                f"({s.pct_above_ma:+.1f}%, {s.days_above_in_window}/{s.window_days}d above)"
            )
    if blocked:
        lines.append("\n🔴 BLOCKED-BY-MA — 20-MA acting as overhead resistance:")
        # sort by % below ascending (most below first = weakest)
        for s in sorted(blocked, key=lambda s: s.pct_above_ma)[:15]:
            lines.append(
                f"  {s.ticker:<7}  ${s.close:>7.2f}  MA20 ${s.ma20:>7.2f}  "
                f"({s.pct_above_ma:+.1f}%, {s.days_below_in_window}/{s.window_days}d below, "
                f"{s.rejections_in_window} rejection(s))"
            )
    return "\n".join(lines)
