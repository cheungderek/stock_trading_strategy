"""
metrics.py - performance & risk stats for backtests.

A backtest is represented as a daily Series of strategy returns (decimal).
Helper to build an equity curve from returns is provided.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd


def equity_curve(returns: pd.Series, capital0: float = 10000.0) -> pd.Series:
    """Compounded equity path from a daily return series (decimal)."""
    r = returns.fillna(0.0)
    return capital0 * (1.0 + r).cumprod()


def cagr(returns: pd.Series) -> float:
    eq = equity_curve(returns)
    n_years = (eq.index[-1] - eq.index[0]).days / 365.25
    if n_years <= 0 or eq.iloc[-1] <= 0:
        return float("nan")
    return float(eq.iloc[-1] / eq.iloc[0]) ** (1.0 / n_years) - 1.0


def sharpe(returns: pd.Series, rf_annual: float = 0.0) -> float:
    """Annualised Sharpe ratio using daily returns, 252 trading days."""
    r = returns.dropna()
    if len(r) < 5:
        return float("nan")
    excess = r - rf_annual / 252.0
    sd = excess.std(ddof=1)
    if sd == 0 or not np.isfinite(sd):
        return float("nan")
    return float(np.sqrt(252.0) * excess.mean() / sd)


def sortino(returns: pd.Series, rf_annual: float = 0.0) -> float:
    r = returns.dropna()
    if len(r) < 5:
        return float("nan")
    excess = r - rf_annual / 252.0
    downside = excess[excess < 0]
    if len(downside) < 2 or downside.std(ddof=1) == 0:
        return float("nan")
    return float(np.sqrt(252.0) * excess.mean() / downside.std(ddof=1))


def max_drawdown(returns: pd.Series) -> float:
    eq = equity_curve(returns)
    peak = eq.cummax()
    dd = (eq / peak) - 1.0
    return float(dd.min())


def calmar(returns: pd.Series) -> float:
    c = cagr(returns)
    mdd = max_drawdown(returns)
    if mdd == 0 or not np.isfinite(mdd):
        return float("nan")
    return float(c / abs(mdd))


def volatility(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * math.sqrt(252.0))


def hit_rate(returns: pd.Series) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return float("nan")
    pos = (r > 0).sum()
    nz = (r != 0).sum()
    return float(pos / nz) if nz else float("nan")


def summary(returns: pd.Series, rf_annual: float = 0.0) -> dict:
    eq = equity_curve(returns)
    return {
        "start": eq.index[0].date(),
        "end":   eq.index[-1].date(),
        "years": round((eq.index[-1] - eq.index[0]).days / 365.25, 2),
        "CAGR":  cagr(returns),
        "Vol":   volatility(returns),
        "Sharpe": sharpe(returns, rf_annual),
        "Sortino": sortino(returns, rf_annual),
        "MaxDD":  max_drawdown(returns),
        "Calmar": calmar(returns),
        "HitRate": hit_rate(returns),
        "Final equity": float(eq.iloc[-1]),
    }


def fmt(s: dict, capital0: float = 10000.0) -> str:
    pct = lambda v: f"{v*100:.2f}%" if isinstance(v, float) and np.isfinite(v) else f"{v}"
    f2 = lambda v: f"{v:.2f}" if isinstance(v, float) and np.isfinite(v) else f"{v}"
    money = lambda v: f"${v:,.0f}"
    return (
        f"  period      {s['start']} -> {s['end']}  ({s['years']} yrs)\n"
        f"  CAGR        {pct(s['CAGR'])}\n"
        f"  Vol         {pct(s['Vol'])}\n"
        f"  Sharpe      {s['Sharpe']:.2f}\n"
        f"  Sortino     {s['Sortino']:.2f}\n"
        f"  Max DD      {pct(s['MaxDD'])}\n"
        f"  Calmar      {f2(s['Calmar'])}\n"
        f"  Hit rate    {pct(s['HitRate'])}\n"
        f"  Final       {money(s['Final equity'])}  (start {money(capital0)})"
    )


def summary_table(strategies: dict) -> pd.DataFrame:
    """strategies: {name: pd.Series of returns}. Returns dataframe of metrics."""
    rows = []
    for name, ret in strategies.items():
        s = summary(ret)
        rows.append({
            "Strategy": name,
            "Years": s["years"],
            "CAGR": f"{s['CAGR']*100:.2f}%",
            "Vol": f"{s['Vol']*100:.2f}%",
            "Sharpe": f"{s['Sharpe']:.2f}",
            "Sortino": f"{s['Sortino']:.2f}",
            "MaxDD": f"{s['MaxDD']*100:.2f}%",
            "Calmar": f"{s['Calmar']:.2f}",
        })
    return pd.DataFrame(rows).set_index("Strategy")


if __name__ == "__main__":
    # quick test
    idx = pd.date_range("2020-01-01", periods=252, freq="B")
    r = pd.Series(np.random.normal(0.0004, 0.01, 252), index=idx)
    print(fmt(summary(r)))
