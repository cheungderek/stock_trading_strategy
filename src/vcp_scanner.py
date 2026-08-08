"""
vcp_scanner.py - Mark Minervini Volatility Contraction Pattern (VCP) detector.

A self-contained port of the VCP detector from ~/backtest/vcp_cup_handle_backtest.py.
Scans a list of tickers and identifies stocks exhibiting a valid VCP setup ready for
breakout, then produces annotated chart PNGs.

Minervini's VCP criteria (simplified):
  1. Prior uptrend: 50-day SMA > 200-day SMA, price within 25% of SMA200.
  2. Base length: 20-200 days (consolidation after an advance).
  3. Base depth: 10%-40% from base high to base low.
  4. Contractions: >=2 pullbacks each with progressively smaller drop% from base high.
  5. Tightness: last 10-day avgTR < 65% of peak 20-day avgTR in base.
  6. Volume dry-up at the right edge (last 5 days < 70% of base avg).
  7. Final close within 15% of base high and NOT yet broken out.

This module also exposes:
  - scan_watchlist_vcp          : strict LIVE setups (all 7 criteria today).
  - scan_watchlist_vcp_forming  : relaxed FORMING setups (most criteria today,
                                  close to but not yet ready for breakout).
  - scan_watchlist_vcp_exits    : LIVE exit tracking for tickers that fired a
                                  LIVE entry on a prior scan; emits an EXIT
                                  when today's close breaks the 10-day low
                                  (Minervini's hard/trailing stop).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import config


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
VCP_MIN_CONTRACTIONS = 2
VCP_MAX_BASE_DAYS = 200
VCP_MAX_DEPTH = 0.40
VCP_MIN_DEPTH = 0.10

# FORMING VCP: relaxed thresholds. A "FORMING" setup is one that has the
# structural VCP shape (uptrend + base + contractions) but is missing one or
# two of the right-edge readout criteria (tightness, volume dry-up, or close
# too far below base high). It's a watch-list: "this one could trigger soon".
FORMING_MIN_CONTRACTIONS = 1          # at least 1 contraction already in place
FORMING_MAX_BASE_DAYS = 260           # allow longer bases
FORMING_MAX_DEPTH = 0.55             # allow deeper bases (still coming together)
FORMING_MIN_DEPTH = 0.06
FORMING_MIN_CRITERIA = 4              # of the 7, must satisfy at least this many
FORMING_MIN_NEAR_HIGH = 0.80          # close >= 80% of base_high (not way back at base_low)

# Live-exit state: separate file so it doesn't collide with the Donchian
# dedup state in results/scan_state.json.
VCP_POSITIONS_FILE = os.path.join(config.RESULTS_DIR, "vcp_positions.json")


# --------------------------------------------------------------------------- #
# Swing pivot helpers
# --------------------------------------------------------------------------- #
def find_swing_highs(high: np.ndarray, order: int = 5) -> np.ndarray:
    n = len(high)
    idx = []
    for i in range(order, n - order):
        w = high[i - order:i + order + 1]
        if high[i] == w.max() and np.sum(w == w.max()) == 1:
            idx.append(i)
    return np.array(idx, dtype=int)


def find_swing_lows(low: np.ndarray, order: int = 5) -> np.ndarray:
    n = len(low)
    idx = []
    for i in range(order, n - order):
        w = low[i - order:i + order + 1]
        if low[i] == w.min() and np.sum(w == w.min()) == 1:
            idx.append(i)
    return np.array(idx, dtype=int)


def atr_array(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    tr = np.empty_like(high, dtype=float)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
    return tr


# --------------------------------------------------------------------------- #
# VCP detector
# --------------------------------------------------------------------------- #
@dataclass
class VCPSignal:
    ticker: str
    date: str
    close: float
    base_high: float
    base_low: float
    base_high_idx: int  # absolute index in df
    pivot_idx: int      # absolute index of last closed bar
    contractions: list  # list of (local_idx, abs_idx, h, l, drop)


def detect_vcp(df: pd.DataFrame, end_idx: int) -> Optional[dict]:
    """
    Detect VCP. `end_idx` = index of most recently closed bar (pivot).
    Returns a dict with base_high, base_low, contractions, base_high_idx, pivot_idx, or None.
    """
    if end_idx < 220:
        return None

    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float) if "High" in df.columns else close
    low = df["Low"].values.astype(float) if "Low" in df.columns else close
    vol = df["Volume"].values.astype(float) if "Volume" in df.columns else np.ones_like(close)

    # Synthesize High/Low from Close if needed (some yfinance returns Close-only)
    if "High" not in df.columns or "Low" not in df.columns:
        high = close.copy()
        low = close.copy()
        for i in range(1, len(close)):
            high[i] = max(close[i], close[i - 1])
            low[i] = min(close[i], close[i - 1])
        # Use a true intraday proxy: high[i] = max(close[i], close[i-1]); low[i] = min(...)

    # 1. Uptrend filter
    sma50 = pd.Series(close).rolling(50).mean().values
    sma200 = pd.Series(close).rolling(200).mean().values
    if not (np.isfinite(sma200[end_idx - 1]) and sma50[end_idx - 1] > sma200[end_idx - 1]):
        return None
    if not (close[end_idx - 1] > sma200[end_idx - 1] * 0.75):
        return None

    # 2. Lookback window & base high
    lookback = min(end_idx, VCP_MAX_BASE_DAYS)
    seg_high = high[end_idx - lookback:end_idx]
    base_high_local = int(np.argmax(seg_high))
    base_high_idx = end_idx - lookback + base_high_local
    base_high = float(seg_high[base_high_local])
    base_len = end_idx - base_high_idx
    if base_len < 20:
        return None

    # 3. Base depth filter
    base_low = float(low[base_high_idx:end_idx].min())
    depth = (base_high - base_low) / base_high
    if not (VCP_MIN_DEPTH <= depth <= VCP_MAX_DEPTH):
        return None

    # 4. Contractions (progressively smaller pullbacks)
    seg_h_after = high[base_high_idx:end_idx]
    seg_l_after = low[base_high_idx:end_idx]
    swing_h_idx = find_swing_highs(seg_h_after, order=5)
    swing_l_idx = find_swing_lows(seg_l_after, order=5)

    initial_drop = depth
    contractions = []
    last_drop = initial_drop
    for sh in swing_h_idx:
        next_lows = swing_l_idx[swing_l_idx > sh]
        if len(next_lows) == 0:
            low_after = seg_l_after[sh:].min()
        else:
            low_after = seg_l_after[sh:next_lows[0] + 1].min()
        sval = seg_h_after[sh]
        drop = (sval - low_after) / sval
        if drop >= 0.02:
            if drop < last_drop * 0.85 or len(contractions) == 0:
                contractions.append((sh, base_high_idx + sh, float(sval), float(low_after), float(drop)))
                last_drop = drop
    if len(contractions) < VCP_MIN_CONTRACTIONS:
        return None
    if not (contractions[-1][4] < contractions[0][4]):
        return None
    if not (contractions[-1][4] <= 0.10):
        return None

    # 5. Tightness
    tr = atr_array(high, low, close)
    atr20 = pd.Series(tr).rolling(20).mean().values
    atr10 = pd.Series(tr).rolling(10).mean().values
    peak_atr = atr20[base_high_idx:end_idx].max()
    cur_atr = atr10[end_idx - 1]
    if not (np.isfinite(peak_atr) and peak_atr > 0 and cur_atr < 0.65 * peak_atr):
        return None

    # 6. Volume dry-up
    base_avg_vol = vol[base_high_idx:end_idx].mean()
    last_vol = vol[end_idx - 5:end_idx].mean()
    if last_vol > 0.70 * base_avg_vol:
        return None

    # 7. Final close near base high and not yet broken out
    final_close = close[end_idx - 1]
    if final_close < base_high * 0.85:
        return None
    if final_close > base_high * 1.005:
        return None

    return {
        "pattern": "VCP",
        "base_high": base_high,
        "base_low": base_low,
        "base_high_idx": base_high_idx,
        "contractions": contractions,
        "pivot_idx": end_idx - 1,
    }


# --------------------------------------------------------------------------- #
# Per-criterion scoring (used by both STRICT and FORMING detectors)
# --------------------------------------------------------------------------- #
def evaluate_vcp_factors(df: pd.DataFrame, end_idx: int) -> Optional[dict]:
    """
    Evaluate the 7 VCP criteria at `end_idx` (index of last closed bar).
    Returns a dict with:
      - criteria_pass: int          number of the 7 criteria satisfied
      - criteria: dict[str,bool]   per-criterion pass/fail map
      - base_high, base_low, base_high_idx, base_len, depth, contractions,
        final_close, final_close_pct_of_high, peak_atr, cur_atr,
        base_avg_vol, last_vol, vol_ratio, cur_atr_ratio
    Returns None if the structural filters (uptrend, min base length, min
    depth) fail - i.e. there is no recognizable VCP to score.
    """
    if end_idx < 220:
        return None

    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float) if "High" in df.columns else close
    low = df["Low"].values.astype(float) if "Low" in df.columns else close
    vol = df["Volume"].values.astype(float) if "Volume" in df.columns else np.ones_like(close)

    if "High" not in df.columns or "Low" not in df.columns:
        high = close.copy()
        low = close.copy()
        for i in range(1, len(close)):
            high[i] = max(close[i], close[i - 1])
            low[i] = min(close[i], close[i - 1])

    criteria: Dict[str, bool] = {}

    # 1. Uptrend filter
    sma50 = pd.Series(close).rolling(50).mean().values
    sma200 = pd.Series(close).rolling(200).mean().values
    uptrend_ok = (np.isfinite(sma200[end_idx - 1])
                  and sma50[end_idx - 1] > sma200[end_idx - 1]
                  and close[end_idx - 1] > sma200[end_idx - 1] * 0.75)
    criteria["uptrend"] = bool(uptrend_ok)
    if not uptrend_ok:
        return None  # structural - no VCP here

    # 2. Lookback window & base high
    lookback = min(end_idx, VCP_MAX_BASE_DAYS)
    seg_high = high[end_idx - lookback:end_idx]
    base_high_local = int(np.argmax(seg_high))
    base_high_idx = end_idx - lookback + base_high_local
    base_high = float(seg_high[base_high_local])
    base_len = end_idx - base_high_idx

    # 3. Base depth filter (relaxed for forming scoring)
    base_low = float(low[base_high_idx:end_idx].min())
    depth = (base_high - base_low) / base_high
    base_ok = (20 <= base_len <= VCP_MAX_BASE_DAYS
               and VCP_MIN_DEPTH <= depth <= VCP_MAX_DEPTH)
    criteria["base_structure"] = bool(base_ok)

    # 4. Contractions
    seg_h_after = high[base_high_idx:end_idx]
    seg_l_after = low[base_high_idx:end_idx]
    swing_h_idx = find_swing_highs(seg_h_after, order=5)
    swing_l_idx = find_swing_lows(seg_l_after, order=5)

    initial_drop = depth
    contractions = []
    last_drop = initial_drop
    for sh in swing_h_idx:
        next_lows = swing_l_idx[swing_l_idx > sh]
        if len(next_lows) == 0:
            low_after = seg_l_after[sh:].min()
        else:
            low_after = seg_l_after[sh:next_lows[0] + 1].min()
        sval = seg_h_after[sh]
        drop = (sval - low_after) / sval
        if drop >= 0.02:
            if drop < last_drop * 0.85 or len(contractions) == 0:
                contractions.append((sh, base_high_idx + sh,
                                     float(sval), float(low_after), float(drop)))
                last_drop = drop
    contractions_ok = (len(contractions) >= VCP_MIN_CONTRACTIONS
                       and contractions[-1][4] < contractions[0][4]
                       and contractions[-1][4] <= 0.10)
    criteria["contractions"] = bool(contractions_ok)

    # 5. Tightness
    tr = atr_array(high, low, close)
    atr20 = pd.Series(tr).rolling(20).mean().values
    atr10 = pd.Series(tr).rolling(10).mean().values
    peak_atr = float(atr20[base_high_idx:end_idx].max())
    cur_atr = float(atr10[end_idx - 1])
    cur_atr_ratio = (cur_atr / peak_atr) if (np.isfinite(peak_atr) and peak_atr > 0) else np.nan
    tightness_ok = (np.isfinite(cur_atr_ratio) and cur_atr_ratio < 0.65)
    criteria["tightness"] = bool(tightness_ok)

    # 6. Volume dry-up
    base_avg_vol = float(vol[base_high_idx:end_idx].mean())
    last_vol = float(vol[end_idx - 5:end_idx].mean())
    vol_ratio = (last_vol / base_avg_vol) if base_avg_vol > 0 else np.nan
    vol_ok = (np.isfinite(vol_ratio) and vol_ratio < 0.70)
    criteria["volume_dryup"] = bool(vol_ok)

    # 7. Final close near base high and not yet broken out
    final_close = float(close[end_idx - 1])
    final_close_pct_of_high = (final_close / base_high) if base_high > 0 else np.nan
    # Not-yet-broken-out AND within 15% below base high.
    close_near_ok = (final_close < base_high * 1.005
                     and final_close > base_high * 0.85)
    criteria["close_near_high"] = bool(close_near_ok)

    criteria_pass = sum(1 for v in criteria.values() if v)

    return {
        "criteria_pass": criteria_pass,
        "criteria": criteria,
        "base_high": base_high,
        "base_low": base_low,
        "base_high_idx": base_high_idx,
        "base_len": int(base_len),
        "depth": float(depth),
        "contractions": contractions,
        "pivot_idx": end_idx - 1,
        "final_close": final_close,
        "final_close_pct_of_high": float(final_close_pct_of_high),
        "peak_atr": peak_atr,
        "cur_atr": cur_atr,
        "cur_atr_ratio": float(cur_atr_ratio) if np.isfinite(cur_atr_ratio) else None,
        "base_avg_vol": base_avg_vol,
        "last_vol": last_vol,
        "vol_ratio": float(vol_ratio) if np.isfinite(vol_ratio) else None,
    }


# --------------------------------------------------------------------------- #
# FORMING VCP detector
# --------------------------------------------------------------------------- #
def detect_vcp_forming(df: pd.DataFrame, end_idx: int) -> Optional[dict]:
    """
    Relaxed detector: report a "FORMING" VCP when the structure is in place
    (uptrend + recognizable base + at least one contraction) but a small
    number of readout criteria fail. This is a watch-list: stocks that may
    trigger the strict LIVE VCP soon.

    Comfort criteria for FORMING:
      - structural (uptrend) passes
      - base length 20-260 days, depth 6-55%
      - at least 1 contraction already showing
      - at least FORMING_MIN_CRITERIA of the 7 criteria satisfied
      - close >= 80% of base_high (i.e. not sitting at the bottom of base)
      - not already broken out (close < base_high * 1.005)
    """
    f = evaluate_vcp_factors(df, end_idx)
    if f is None:
        return None

    bh, bl = f["base_high"], f["base_low"]
    cr = f["criteria"]
    final_close = f["final_close"]

    # Structural shape (relaxed)
    base_shape_ok = (20 <= f["base_len"] <= FORMING_MAX_BASE_DAYS
                     and FORMING_MIN_DEPTH <= f["depth"] <= FORMING_MAX_DEPTH)
    if not base_shape_ok:
        return None
    # Need at least 1 contraction
    if len(f["contractions"]) < FORMING_MIN_CONTRACTIONS:
        return None
    # Close should be in the upper part of the base (potentially near breakout)
    if final_close < bh * FORMING_MIN_NEAR_HIGH:
        return None
    # Already broken out? Then this is a strict VCP, not "forming"
    if final_close > bh * 1.005:
        return None
    # Need most criteria
    if f["criteria_pass"] < FORMING_MIN_CRITERIA:
        return None

    # Build a friendly "missing" list so the user knows what's holding it back
    missing = [name for name, ok in cr.items()
               if not ok and name != "close_near_high"]
    # close_near_high failing usually just means the stock needs to climb a bit
    if not cr["close_near_high"] and "close_near_high" not in missing:
        missing.append("close_near_high")

    return {
        "pattern": "VCP_FORMING",
        "base_high": bh,
        "base_low": bl,
        "base_high_idx": f["base_high_idx"],
        "contractions": f["contractions"],
        "pivot_idx": f["pivot_idx"],
        "criteria_pass": f["criteria_pass"],
        "criteria": cr,
        "missing": missing,
        "depth_pct": round(f["depth"] * 100, 2),
        "base_len_days": f["base_len"],
        "final_close": final_close,
        "pct_below_base_high": round((bh - final_close) / bh * 100, 2),
        "cur_atr_ratio": (round(f["cur_atr_ratio"] * 100, 1)
                          if f["cur_atr_ratio"] is not None else None),
        "vol_ratio": (round(f["vol_ratio"] * 100, 1)
                      if f["vol_ratio"] is not None else None),
    }


# --------------------------------------------------------------------------- #
# Live-exit tracking (position state file)
# --------------------------------------------------------------------------- #
def _load_vcp_positions() -> Dict:
    """Open positions previously entered on VCP LIVE signals. Each entry:
        { ticker: {"entry_date": "YYYY-MM-DD",
                    "base_high": float,
                    "entry_close": float,
                    "stop": float          # 10-day low at the time of entry} }
    """
    if not os.path.exists(VCP_POSITIONS_FILE):
        return {}
    try:
        with open(VCP_POSITIONS_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_vcp_positions(positions: Dict) -> None:
    os.makedirs(os.path.dirname(VCP_POSITIONS_FILE), exist_ok=True)
    with open(VCP_POSITIONS_FILE, "w") as fh:
        json.dump(positions, fh, indent=2)


def _ten_day_low(df: pd.DataFrame, at_idx: int) -> float:
    """10-day low of bars strictly before `at_idx` (Minervini trailing stop)."""
    low = df["Low"].astype(float) if "Low" in df.columns else df["Close"].astype(float)
    start = max(0, at_idx - 10)
    return float(low.iloc[start:at_idx].min())


def scan_watchlist_vcp_exits(df_dict: dict,
                             live_entries: Optional[dict] = None) -> Tuple[dict, dict, dict]:
    """
    Track live exits for VCP entries.

    Logic:
      1. Open `results/vcp_positions.json` to load existing VCP positions.
      2. For each OPEN position, check whether today's close has broken its
         trailing 10-day-low stop. If yes, emit EXIT and remove position.
      3. For each NEW VCP LIVE setup in `live_entries`, register a new position
         with the current 10-day low as its trailing stop.

    Returns tuple: (exits, positions_opened, positions_after)
      exits:           {ticker: exit_info}                      - new exit alerts
      positions_opened: {ticker: pos_info}                      - new VCP entries today
      positions_after:  full positions dict (still-open only)           - for caller info
    """
    positions = _load_vcp_positions()
    exits: Dict[str, dict] = {}
    today_idx = -1  # last closed bar

    # Check open positions for stop hits
    to_remove = []
    for ticker, pos in positions.items():
        df = df_dict.get(ticker)
        if df is None or len(df) < 11:
            continue
        today_close = float(df["Close"].iloc[today_idx])
        today_date = df.index[today_idx].strftime("%Y-%m-%d")
        rolling_stop = _ten_day_low(df, len(df) - 1)
        # Stop = max(stored stop, current 10-day low) -> trailing ratchets up
        stop = max(pos.get("stop", 0.0), rolling_stop)
        pos["stop"] = round(stop, 4)  # update trailing stop

        if today_close <= stop:
            exits[ticker] = {
                "ticker": ticker,
                "exit_date": today_date,
                "exit_close": round(today_close, 2),
                "stop": round(stop, 2),
                "entry_date": pos.get("entry_date"),
                "entry_close": pos.get("entry_close"),
                "base_high": pos.get("base_high"),
                "pct_from_entry": round((today_close - pos["entry_close"])
                                        / pos["entry_close"] * 100, 2),
            }
            to_remove.append(ticker)

    for t in to_remove:
        positions.pop(t, None)

    # Register new positions for tickers that fired a LIVE VCP today
    opened: Dict[str, dict] = {}
    if live_entries:
        for ticker, info in live_entries.items():
            df = df_dict.get(ticker)
            if df is None or len(df) < 11:
                continue
            # Skip if already in positions / exits today (no duplicates)
            if ticker in positions or ticker in exits:
                continue
            today_close = float(df["Close"].iloc[-1])
            today_date = df.index[-1].strftime("%Y-%m-%d")
            stop = _ten_day_low(df, len(df) - 1)
            new_pos = {
                "entry_date": today_date,
                "base_high": float(info["base_high"]),
                "entry_close": round(today_close, 2),
                "stop": round(stop, 4),
            }
            positions[ticker] = new_pos
            opened[ticker] = new_pos

    _save_vcp_positions(positions)
    return exits, opened, positions


def vcp_forming_summary(forming_signals: dict) -> str:
    """Summary of FORMING VCP setups (the watch-list)."""
    if not forming_signals:
        return ("📊 VCP FORMING SCAN: no tickers are in the process of building a VCP "
                "(relaxed criteria) today.")
    lines = [f"📊 VCP FORMING — {len(forming_signals)} ticker(s) building toward a VCP setup:"]
    # Sort by how close the close is to base_high (smaller % below = closer to breakout first)
    sorted_items = sorted(forming_signals.items(),
                          key=lambda kv: kv[1]["pct_below_base_high"])
    for ticker, info in sorted_items[:15]:
        n_c = len(info["contractions"])
        missing = ", ".join(info["missing"]) if info["missing"] else "none"
        lines.append(
            f"\n🟡 FORMING {ticker}  ({info['criteria_pass']}/7 criteria)\n"
            f"  Close ${info['final_close']:.2f}  |  Base high ${info['base_high']:.2f}  "
            f"({info['pct_below_base_high']:.1f}% below breakout)\n"
            f"  Base length {info['base_len_days']}d  |  Depth {info['depth_pct']:.1f}%  "
            f"|  Contractions: {n_c}\n"
            f"  Missing: {missing}"
        )
    return "\n".join(lines)


def vcp_exit_summary(exits: dict) -> str:
    """Summary of live VCP exits (positions hitting the 10-day-low stop)."""
    if not exits:
        return "📊 VCP EXITS: no open VCP positions hit their 10-day-low stop today."
    lines = [f"📊 VCP EXITS — {len(exits)} position(s) stopped out:"]
    for ticker, info in exits.items():
        lines.append(
            f"\n🔴 EXIT  {ticker}  ({info['exit_date']})\n"
            f"  Close ${info['exit_close']:.2f}  broke 10d-low stop ${info['stop']:.2f}\n"
            f"  Entered {info['entry_date']} @ ${info['entry_close']:.2f}  "
            f"-> {info['pct_from_entry']:+.1f}% since entry"
        )
    return "\n".join(lines)


def scan_watchlist_vcp(df_dict: dict) -> dict:
    """
    Run VCP detector on the LAST closed bar of each ticker's dataframe.
    Returns: {ticker: info_dict} for tickers that currently match (LIVE setups).

    'LIVE' means: as of today's close, all 7 VCP criteria are satisfied and the
    setup has not yet broken out. The yellow band on the chart ends at today's date.
    """
    out = {}
    for ticker, df in df_dict.items():
        if len(df) < 220:
            continue
        info = detect_vcp(df, len(df) - 1)
        if info is not None:
            info["ticker"] = ticker
            info["date"] = df.index[-1].strftime("%Y-%m-%d")
            info["close"] = float(df["Close"].iloc[-1])
            info["status"] = "LIVE"
            out[ticker] = info
    return out


def scan_watchlist_vcp_historical(df_dict: dict, lookback_days: int = 250) -> dict:
    """
    For each ticker, find the MOST RECENT date in the last `lookback_days` trading
    days when a VCP setup was detected. Useful for charting "most recent VCP" even
    if today's bar does not satisfy the criteria.

    Returns: {ticker: info_dict} where:
      - info["status"] = "LIVE" if the latest detection IS today
      - info["status"] = "HISTORICAL" if the latest detection is older than today
      - info["days_ago"] = how many trading days ago the most recent VCP fired
    """
    out = {}
    for ticker, df in df_dict.items():
        if len(df) < 220:
            continue
        n = len(df)
        # scan last lookback_days bars, newest first, return first hit
        scan_start = max(220, n - lookback_days)
        most_recent_hit = None
        for i in range(n - 1, scan_start - 1, -1):
            info = detect_vcp(df, i)
            if info is not None:
                info["ticker"] = ticker
                info["date"] = df.index[i].strftime("%Y-%m-%d")
                info["close"] = float(df["Close"].iloc[i])
                info["days_ago"] = n - 1 - i
                info["status"] = "LIVE" if i == n - 1 else "HISTORICAL"
                most_recent_hit = info
                break  # newest-first, stop at first match
        if most_recent_hit is not None:
            out[ticker] = most_recent_hit
    return out


def scan_watchlist_vcp_forming(df_dict: dict) -> dict:
    """
    Run the FORMING VCP detector on each ticker's LAST closed bar.
    Returns: {ticker: forming_info_dict} for tickers that are structurally
    building a VCP but not yet satisfying all 7 strict criteria.

    A ticker already reported by the strict LIVE scan (scan_watchlist_vcp)
    will still appear here (since strict satisfies the forming criteria too),
    but callers usually skip forming for tickers that are LIVE.
    """
    out = {}
    for ticker, df in df_dict.items():
        if len(df) < 220:
            continue
        info = detect_vcp_forming(df, len(df) - 1)
        if info is not None:
            info["ticker"] = ticker
            info["date"] = df.index[-1].strftime("%Y-%m-%d")
            info["status"] = "FORMING"
            out[ticker] = info
    return out


def vcp_signal_summary(signals: dict) -> str:
    """Summary for LIVE VCP signals (today's closes satisfy all criteria)."""
    if not signals:
        return "📊 VCP scan (LIVE): no tickers satisfy all 7 VCP criteria as of today's close."
    lines = [f"📊 VCP LIVE SCAN — {len(signals)} ticker(s) currently valid:"]
    for ticker, info in signals.items():
        n_c = len(info["contractions"])
        last_drop = info["contractions"][-1][4] * 100
        lines.append(
            f"\n🟢 LIVE    {ticker}  ({info['date']})\n"
            f"  Close ${info['close']:.2f}  |  Base high ${info['base_high']:.2f}  |  Base low ${info['base_low']:.2f}\n"
            f"  Contractions: {n_c} (last drop: {last_drop:.2f}%)\n"
            f"  BUY pivot: ${info['base_high']:.2f}  (breakout > base high on volume)"
        )
    return "\n".join(lines)


def vcp_historical_summary(hist_signals: dict) -> str:
    """Summary of most recent VCP setup per ticker (even if not LIVE today)."""
    if not hist_signals:
        return "📊 VCP history: no VCP setups detected in the lookback window."
    lines = ["📊 VCP MOST-RECENT-SETUP PER TICKER:"]
    # Sort: LIVE first, then HISTORICAL by days_ago ascending
    sorted_items = sorted(hist_signals.items(),
                          key=lambda kv: (kv[1]["status"] != "LIVE",
                                          kv[1].get("days_ago", 9999)))
    for ticker, info in sorted_items:
        n_c = len(info["contractions"])
        last_drop = info["contractions"][-1][4] * 100
        if info["status"] == "LIVE":
            tag = f"🟢 LIVE  ({info['date']}, today)"
        else:
            tag = f"⏪ HIST   ({info['date']}, {info['days_ago']} trading days ago)"
        lines.append(
            f"\n  {tag}  {ticker}\n"
            f"    Pivot @ ${info['close']:.2f}  |  Base high ${info['base_high']:.2f}\n"
            f"    Contractions: {n_c} (last drop: {last_drop:.2f}%)"
        )
    return "\n".join(lines)
