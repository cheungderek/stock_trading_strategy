"""
run_all.py - run all six survivors side-by-side on the same date range, print a
comparison table, and save an equity-curve PNG.

Usage:
  python3 src/run_all.py
  python3 src/run_all.py --start 2015-01-01 --end 2024-12-31
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import data
import engine
import metrics
import strategies as S


# Universe subsets per strategy (use tickers actually available in the panel)
def available(panel, candidates):
    return [t for t in candidates if t in panel.columns]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--cost_bps", type=float, default=2.0)
    ap.add_argument("--capital", type=float, default=10000.0)
    args = ap.parse_args()

    print(f"Fetching universe data {args.start} -> {args.end} ...\n")
    df_dict = data.fetch_universe(start=args.start, end=args.end)
    print(f"\nLoaded {len(df_dict)} tickers.\n")

    panel = data.aligned_panel(df_dict)
    # Pad with cash proxy BIL if missing
    if "BIL" not in panel.columns and "BIL" in df_dict:
        panel["BIL"] = df_dict["BIL"]["Close"]
    print("Final price panel shape:", panel.shape)

    # Define candidate universes per strategy
    s1_uni = ["SPY", "QQQ", "IWM", "DIA", "XIC.TO", "XSP.TO", "XBB.TO", "GLD", "USO", "FXC"]
    s5_uni = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "VNQ", "XIC.TO", "XBB.TO"]
    s7_uni = ["SPY", "XIC.TO"]
    s8_uni = ["SPY", "XIC.TO"]
    s9_uni = ["SPY", "AGG", "VNQ", "GLD", "DBC", "XIC.TO", "XBB.TO", "FXC"]
    s10_uni = ["SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV", "XLI", "XIC.TO", "XBB.TO"]

    # Filter to available
    s1_uni = [t for t in s1_uni if t in panel.columns]
    s5_uni = [t for t in s5_uni if t in panel.columns]
    s7_uni = [t for t in s7_uni if t in panel.columns]
    s8_uni = [t for t in s8_uni if t in panel.columns]
    s9_uni = [t for t in s9_uni if t in panel.columns]
    s10_uni = [t for t in s10_uni if t in panel.columns]

    print("\nRunning strategies ...")
    strategies_returns = {}

    name = "S1_TSMOM"
    print("  -", name)
    w = S.s1_tsmom(panel, s1_uni, lookback=252, rebalance="monthly")
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    name = "S5_Donchian"
    print("  -", name)
    w = S.s5_donchian(panel, s5_uni, entry_window=20, exit_window=10,
                      risk_per_trade=0.01, max_positions=5)
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    name = "S7_Halloween"
    print("  -", name)
    w = S.s7_halloween(panel, s7_uni)
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    name = "S8_TurnOfMonth"
    print("  -", name)
    w = S.s8_turn_of_month(panel, s8_uni)
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    name = "S9_RiskParity"
    print("  -", name)
    w = S.s9_risk_parity(panel, s9_uni, vol_lookback=60, target_vol=0.10)
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    name = "S10_SectorRotation"
    print("  -", name)
    w = S.s10_sector_rotation(panel, s10_uni, rank_lookback=126, top_n=3,
                               vol_lookback=20, target_vol=0.15)
    strategies_returns[name] = engine.backtest(w, panel, cost_bps=args.cost_bps)

    # Benchmark: SPY buy-and-hold
    if "SPY" in panel.columns:
        strategies_returns["BENCH_SPY"] = engine.buy_and_hold("SPY", panel)
    if "XIC.TO" in panel.columns:
        strategies_returns["BENCH_XIC.TO"] = engine.buy_and_hold("XIC.TO", panel)

    # Truncate all to common index
    common_idx = pd.concat(strategies_returns, axis=1).index
    for k, v in strategies_returns.items():
        strategies_returns[k] = v.reindex(common_idx).fillna(0.0)
    common = common_idx

    # Print comparison
    print("\n" + "=" * 90)
    print(f"  SIDE-BY-SIDE BACKTEST  ({common[0].date()} -> {common[-1].date()})")
    print(f"  Capital=${args.capital:,.0f}  Cost={args.cost_bps} bps/trade")
    print("=" * 90)
    df_metrics = metrics.summary_table(strategies_returns)
    print(df_metrics.to_string())

    # Save CSV
    out_dir = HERE.parent / "results"
    out_dir.mkdir(exist_ok=True)
    df_metrics.to_csv(out_dir / "metrics.csv")
    # Save returns
    rets_df = pd.concat(strategies_returns, axis=1)
    rets_df.to_csv(out_dir / "returns.csv")
    # Save weights summary
    df_metrics.to_csv(out_dir / "metrics.csv")

    # Equity curve plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        eq = pd.DataFrame({k: metrics.equity_curve(v, args.capital)
                           for k, v in strategies_returns.items()})
        fig, ax = plt.subplots(figsize=(12, 6))
        for c in eq.columns:
            ax.plot(eq.index, eq[c], label=c, linewidth=1.4)
        ax.set_title(f"Strategy comparison ({common[0].date()} -> {common[-1].date()})")
        ax.set_xlabel("Date"); ax.set_ylabel("Equity ($)")
        ax.legend(loc="upper left", fontsize=9, ncol=2)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        out_png = out_dir / "equity_curve.png"
        fig.savefig(out_png, dpi=120)
        print(f"\nEquity curve PNG saved to: {out_png}")
    except Exception as e:
        print("Plot skipped:", e)

    print(f"\nMetrics saved to: {out_dir}/metrics.csv")
    print(f"Daily returns saved to: {out_dir}/returns.csv")

    # Pick best by Sharpe
    sh = [(k, metrics.sharpe(v)) for k, v in strategies_returns.items()
          if not k.startswith("BENCH")]
    sh.sort(key=lambda x: x[1] if np.isfinite(x[1]) else -9e9, reverse=True)
    print("\nRANKING BY SHARPE:")
    for i, (k, v) in enumerate(sh, 1):
        print(f"  {i}. {k:<25} Sharpe = {v:.2f}")


if __name__ == "__main__":
    main()
