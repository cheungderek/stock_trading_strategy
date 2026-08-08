"""
strategies.py - the six survivor rules, each as a function returning a
target-weights DataFrame (index=date, columns=tickers) decided using only
prices available up to and including that date.

The engine applies weights with a 1-day lag, so no look-ahead.

S1  TSMOM (price momentum, 252d, monthly, long-or-cash)
S5  Donchian 20/10 breakout (event-driven per-asset, long-or-flat)
S7  Sell in May / Halloween (Nov-Apr equity, May-Oct cash, annual)
S8  Turn-of-month (4-day monthly window)
S9  Risk parity vol-scaling (8-ETF, monthly)
S10 Sector rotation (top-3 by 126d return, vol-scaled, monthly)

All functions take:
  price_panel: pd.DataFrame of close prices (one column per ticker)
  universe_subset: list of tickers to use (must be columns of price_panel)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _daily_returns(df: pd.DataFrame) -> pd.DataFrame:
    return df.pct_change().fillna(0.0)


def _realized_vol(rets: pd.Series, window: int = 20) -> float:
    """Annualized realized vol of last `window` day returns."""
    if len(rets) < max(window, 5):
        window = max(5, len(rets))
    return float(rets.tail(window).std(ddof=1) * np.sqrt(TRADING_DAYS))


def _month_end_mask(idx: pd.DatetimeIndex) -> pd.Series:
    """Boolean series: True on the last trading day of each month."""
    s = pd.Series(idx, index=idx)
    next_month = s.shift(-1).dt.month
    return (next_month != s.dt.month) | (next_month.isna())


# --------------------------------------------------------------------------- #
# S1 - TSMOM (long-or-cash)
# --------------------------------------------------------------------------- #
def s1_tsmom(price_panel: pd.DataFrame,
             universe_subset: list,
             lookback: int = 252,
             rebalance: str = "monthly") -> pd.DataFrame:
    """
    Long any ticker whose trailing `lookback` return is positive, else cash.
    Equal-dollar weight among long holdings.
    """
    close = price_panel[universe_subset].copy()
    rets_full = _daily_returns(close)
    cum_return = (1.0 + rets_full).rolling(lookback).apply(
        np.prod, raw=True) - 1.0

    # Build weights only on rebalance days, then forward-fill.
    w = pd.DataFrame(0.0, index=close.index, columns=universe_subset)
    if rebalance == "monthly":
        mask = _month_end_mask(close.index).values
    else:
        mask = np.ones(len(close.index), dtype=bool)

    for i, dt in enumerate(close.index):
        if not mask[i]:
            continue
        cr = cum_return.iloc[i]
        longs = cr[cr > 0].index.tolist()
        if longs:
            share = 1.0 / len(longs)
            for t in longs:
                w.loc[dt, t] = share
    # cash column (BIL) absorbs the remaining weight via ffill when nothing held.
    if "BIL" in price_panel.columns and "BIL" not in w.columns:
        # add a cash column implied = 1 - sum(others)
        cash_w = (1.0 - w.sum(axis=1)).clip(lower=0.0)
        w["BIL"] = cash_w
    elif "BIL" in universe_subset:
        w["BIL"] = (1.0 - w.drop(columns=["BIL"], errors="ignore").sum(axis=1)).clip(lower=0.0)
    return w.fillna(0.0)


# --------------------------------------------------------------------------- #
# S5 - Donchian 20/10 breakout (per-asset long-or-flat, sized by 1% risk)
# --------------------------------------------------------------------------- #
def s5_donchian(price_panel: pd.DataFrame,
                universe_subset: list,
                entry_window: int = 20,
                exit_window: int = 10,
                risk_per_trade: float = 0.01,
                atr_window: int = 20,
                max_positions: int = 5) -> pd.DataFrame:
    """
    Per-asset channel breakout, risk-sized weight:
        - entry: today's close > max(high over past entry_window)
        - exit:   today's close < min(low   over past exit_window)
      (no short sleeve for simplicity and to allow broad retail use)
    Weight on entry = risk_per_trade / (ATR/price), capped at 20% of equity per
    name; total exposure capped at max_positions * 20% = 100%.
    Cash weight = whatever's left, in BIL if present.
    """
    close = price_panel.copy()
    idx = close.index
    # state
    in_pos = {t: False for t in universe_subset}
    weights = {t: 0.0 for t in universe_subset}
    rows = []

    def atr_array(high, low, c, n=20):
        tr = pd.DataFrame(index=c.index)
        tr["h_l"] = high - low
        tr["h_pc"] = (high - c.shift(1)).abs()
        tr["l_pc"] = (low - c.shift(1)).abs()
        tr["tr"] = tr[["h_l", "h_pc", "l_pc"]].max(axis=1)
        return tr["tr"].rolling(n).mean()

    atrs = {t: atr_array(close[t + "_h"] if (t + "_h") in price_panel else close[t],
                         close[t], close[t], atr_window)
            for t in universe_subset}
    # we only have Close in this panel; approximate ATR using close-to-close range:
    # Fall back to (close - close.shift(1)).abs() as TR proxy if high/low missing.
    atrs = {}
    for t in universe_subset:
        if {"High" if False else None} or False:
            pass
        c = close[t]
        tr = (c - c.shift(1)).abs()
        atrs[t] = tr.rolling(atr_window).mean()

    for i, dt in enumerate(idx):
        if i < max(entry_window, exit_window) + 1:
            rows.append([dt] + [0.0] * len(universe_subset))
            continue
        for t in universe_subset:
            px = close[t]
            cur = px.iloc[i]
            entry_thresh = px.iloc[i - entry_window:i].max()
            exit_thresh = px.iloc[i - exit_window:i].min()
            # use simple proxy for high/low since panel is closes-only:
            entry_thresh_hi = px.iloc[i - entry_window - 1:i].max()
            exit_thresh_lo = px.iloc[i - exit_window - 1:i].min()
            atr_val = atrs[t].iloc[i]
            px_now = cur

            if not in_pos[t]:
                # entry signal: today's close > prior `entry_window` highs (using high proxy)
                if cur > entry_thresh_hi and np.isfinite(atr_val) and atr_val > 0:
                    # risk-sized weight: dollar vol risk per share = ATR/price
                    risk_pct = atr_val / px_now
                    if risk_pct > 0:
                        w_t = min(0.20, risk_per_trade / risk_pct)
                    else:
                        w_t = 0.0
                    # cap number of simultaneous positions
                    cur_positions = sum(1 for k in in_pos if in_pos[k])
                    if cur_positions < max_positions:
                        in_pos[t] = True
                        weights[t] = w_t
            else:
                # exit if close <= exit_window_min (using close-based proxy)
                if cur < exit_thresh_lo:
                    in_pos[t] = False
                    weights[t] = 0.0
                # else keep but clip weight (no reload)
        rows.append([dt] + [weights[t] for t in universe_subset])

    w = pd.DataFrame(rows, columns=["Date"] + universe_subset).set_index("Date")
    w.index = pd.to_datetime(w.index)
    # cash absorbs leftover
    if "BIL" in price_panel.columns and "BIL" not in w.columns:
        w["BIL"] = (1.0 - w.sum(axis=1)).clip(lower=0.0)
    return w.fillna(0.0)


# --------------------------------------------------------------------------- #
# S7 - Sell-in-May / Halloween
# --------------------------------------------------------------------------- #
def s7_halloween(price_panel: pd.DataFrame,
                 universe_subset: list,
                 in_months: tuple = (11, 12, 1, 2, 3, 4)) -> pd.DataFrame:
    """
    Equal-dollar weight across `universe_subset` (e.g., SPY + XIC.TO) during
    Nov-Apr; otherwise cash (BIL).
    """
    close = price_panel[universe_subset].copy()
    w = pd.DataFrame(0.0, index=close.index, columns=universe_subset)
    months = close.index.month
    in_mask = pd.Series(months, index=close.index).isin(in_months)
    share = 1.0 / len(universe_subset)
    for t in universe_subset:
        w.loc[in_mask, t] = share
    if "BIL" in price_panel.columns:
        cash_w = (1.0 - w.sum(axis=1)).clip(lower=0.0)
        w["BIL"] = cash_w
    return w.fillna(0.0)


# --------------------------------------------------------------------------- #
# S8 - Turn-of-month
# --------------------------------------------------------------------------- #
def s8_turn_of_month(price_panel: pd.DataFrame,
                     universe_subset: list,
                     days_before_month_end: int = 1,
                     days_into_month: int = 3) -> pd.DataFrame:
    """
    Long `universe_subset` (SPY, XIC.TO) from the last trading day of month T
    through the first `days_into_month` trading days of month T+1; cash otherwise.
    """
    close = price_panel[universe_subset].copy()
    idx = close.index
    month_end = _month_end_mask(idx)
    # last `days_before_month_end` trading days of month + first N trading days of next
    in_window = pd.Series(False, index=idx)
    # mark: each day whose month-end flag is True ORNING was within window
    # Simple approach: build per-month list
    s = pd.Series(idx, index=idx)
    grp = s.groupby([s.index.year, s.index.month])
    for (_, mo), dates in grp:
        dates = list(dates)
        # last N1 days of this month
        n1 = min(days_before_month_end, len(dates))
        for d in dates[-n1:]:
            in_window.loc[d] = True
        # first N2 days of *next* month -> mark after the loop
    # Now mark the first N trading days of each month
    first_grp = s.groupby([s.index.year, s.index.month])
    for (_, mo), dates in first_grp:
        dates = list(dates)
        for d in dates[:days_into_month]:
            in_window.loc[d] = True

    w = pd.DataFrame(0.0, index=idx, columns=universe_subset)
    share = 1.0 / len(universe_subset)
    for t in universe_subset:
        w.loc[in_window, t] = share
    if "BIL" in price_panel.columns:
        w["BIL"] = (1.0 - w.sum(axis=1)).clip(lower=0.0)
    return w.fillna(0.0)


# --------------------------------------------------------------------------- #
# S9 - Risk parity vol-scaling (8-ETF)
# --------------------------------------------------------------------------- #
def s9_risk_parity(price_panel: pd.DataFrame,
                   universe_subset: list,
                   vol_lookback: int = 60,
                   target_vol: float = 0.10,
                   rebalance: str = "monthly") -> pd.DataFrame:
    """
    Equal-risk-contribution weights: w_i = (1/sigma_i) / sum(1/sigma_j).
    Scale all weights so portfolio realized vol = target_vol.
    """
    close = price_panel[universe_subset].copy()
    rets = _daily_returns(close)

    w = pd.DataFrame(0.0, index=close.index, columns=universe_subset)
    if rebalance == "monthly":
        mask = _month_end_mask(close.index).values
    else:
        mask = np.ones(len(close.index), dtype=bool)

    for i, dt in enumerate(close.index):
        if not mask[i]:
            continue
        sigmas = np.array([_realized_vol(rets[t].iloc[:i + 1], vol_lookback)
                           for t in universe_subset])
        if np.any(sigmas <= 0) or np.any(~np.isfinite(sigmas)):
            continue
        inv = 1.0 / sigmas
        w_raw = inv / inv.sum()
        # estimate portfolio vol: weighted asset vols (diagonal approx)
        port_vol = np.sqrt((w_raw ** 2 * sigmas ** 2).sum())
        if port_vol > 0:
            scale = target_vol / port_vol
            w.loc[dt, universe_subset] = w_raw * scale
    if "BIL" in price_panel.columns:
        w["BIL"] = (1.0 - w.sum(axis=1)).clip(lower=0.0)
    return w.fillna(0.0)


# --------------------------------------------------------------------------- #
# S10 - Sector rotation: top 3 by 126d total return, vol-scaled
# --------------------------------------------------------------------------- #
def s10_sector_rotation(price_panel: pd.DataFrame,
                        universe_subset: list,
                        rank_lookback: int = 126,
                        top_n: int = 3,
                        vol_lookback: int = 20,
                        target_vol: float = 0.15,
                        rebalance: str = "monthly") -> pd.DataFrame:
    """
    Rank by trailing `rank_lookback` total return; hold top `top_n`; size each
    by inverse trailing vol; rescale so total <> vol = target_vol.
    """
    close = price_panel[universe_subset].copy()
    rets = _daily_returns(close)
    cum_return = (1.0 + rets).rolling(rank_lookback).apply(np.prod, raw=True) - 1.0

    w = pd.DataFrame(0.0, index=close.index, columns=universe_subset)
    if rebalance == "monthly":
        mask = _month_end_mask(close.index).values
    else:
        mask = np.ones(len(close.index), dtype=bool)

    for i, dt in enumerate(close.index):
        if not mask[i]:
            continue
        cr = cum_return.iloc[i]
        if cr.dropna().shape[0] < top_n:
            continue
        ranked = cr.sort_values(ascending=False)
        held = ranked.head(top_n).index.tolist()
        sigmas = np.array([
            max(_realized_vol(rets[t].iloc[:i + 1], vol_lookback), 1e-6)
            for t in held
        ])
        inv = 1.0 / sigmas
        w_raw = inv / inv.sum()
        port_vol = np.sqrt((w_raw ** 2 * sigmas ** 2).sum())
        if port_vol > 0:
            scale = target_vol / port_vol
            for t, ww in zip(held, w_raw * scale):
                w.loc[dt, t] = float(ww)
    if "BIL" in price_panel.columns:
        w["BIL"] = (1.0 - w.sum(axis=1)).clip(lower=0.0)
    return w.fillna(0.0)
