"""
engine.py - backtest engine that translates a target-weights DataFrame into a
daily return series.

Conventions
-----------
- weights dataframe: index=date, columns=tickers, values=target weight (decimal,
  sums to ~1.0; can hold cash proxy like BIL).
- Weights at date t are *decided* using prices up to t, but *applied* at t+1
  (no look-ahead). Daily strategy return on t+1 = sum(weights[t] * asset_returns[t+1]).
- Transaction cost: cost_bps applied to |weighted turnover| each rebalance day.
- A 'BIL' ticker is treated as the cash proxy if present; we treat it like any
  other ticker (its daily return is just BIL's own return).

A 'buy & hold' helper is included for benchmarks.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def asset_daily_returns(price_panel: pd.DataFrame) -> pd.DataFrame:
    """Simple pct_change daily returns of a wide price dataframe."""
    return price_panel.pct_change().fillna(0.0)


def apply_cost(weights: pd.DataFrame, cost_bps: float = 2.0,
               rebalance_only_on_change: bool = True) -> pd.Series:
    """
    Compute a daily cost series in returns.

    Turnover at date t = sum(|w[t] - w[t-1]|) on the columns belonging to the
    strategy (excluding cash proxy 'BIL' if present - BIL movements are nearly
    free in real trading; we still charge for them but only if the strategy
    explicitly rotates out of BIL).
    """
    if weights.empty:
        return pd.Series(dtype=float)
    diff = weights.diff().abs().sum(axis=1).fillna(0.0)
    if not rebalance_only_on_change:
        # charge every day the weights change
        pass
    cost_per_day = diff * (cost_bps / 10000.0)
    return cost_per_day


def backtest(weights: pd.DataFrame, price_panel: pd.DataFrame,
             cost_bps: float = 2.0) -> pd.Series:
    """
    weights: target weights decided using info up to t (applied at t+1).
    price_panel: close prices (one column per asset including any cash proxy).
    Returns: daily strategy returns (decimal).
    """
    # Align both indexes
    cols = [c for c in weights.columns if c in price_panel.columns]
    w = weights[cols].reindex(price_panel.index).ffill().fillna(0.0)
    rets = asset_daily_returns(price_panel[cols])

    # Apply weights with a 1-day lag to avoid look-ahead
    w_lagged = w.shift(1).fillna(0.0)
    gross = (w_lagged * rets).sum(axis=1)

    # Transaction cost (lagged to be charged when weights change is realised)
    cost = apply_cost(weights[cols], cost_bps=cost_bps).shift(1).fillna(0.0)
    return (gross - cost).rename("ret")


def buy_and_hold(ticker: str, price_panel: pd.DataFrame) -> pd.Series:
    p = price_panel[ticker].dropna()
    return p.pct_change().fillna(0.0).rename(ticker)


def equal_weight_hold(tickers: list, price_panel: pd.DataFrame) -> pd.Series:
    """Equal-weight buy-and-hold benchmark across N tickers, rebalanced monthly.
    Used as a naive benchmark."""
    p = price_panel[tickers].dropna(how="all")
    rets = p.pct_change().fillna(0.0)
    # Build monthly-rebalanced equal weights
    w = pd.DataFrame(1.0 / len(tickers), index=rets.index, columns=tickers)
    # only rebalance at month-end
    mask = w.index.to_series().groupby([w.index.year, w.index.month]).transform("size")
    # easier: use month-end flag
    is_month_end = w.index.to_series().shift(-1).dt.month != w.index.to_series().dt.month
    w_eq = pd.DataFrame(index=w.index, columns=tickers, dtype=float)
    cur = np.array([1.0 / len(tickers)] * len(tickers))
    for i, dt in enumerate(w.index):
        if i == 0 or is_month_end.iloc[i - 1]:
            cur = np.array([1.0 / len(tickers)] * len(tickers))
        w_eq.iloc[i] = cur
    return backtest(w_eq, price_panel)
