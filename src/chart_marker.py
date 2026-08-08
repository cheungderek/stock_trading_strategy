"""
chart_marker.py - draw annotated PNG charts of VCP / Donchian 20/10 buy & sell
points on stocks that currently exhibit a signal.

Both strategies are saved side-by-side in results/charts/. Each chart shows the
price history, the strategy's reference levels (channels / base), and the exact
buy point (entry) and sell point (exit) along with the rule that triggered it.

Strategy: VCP (Minervini)
  - Stars on contraction swing highs (progressively smaller pullbacks).
  - Horizontal line at base_high labeled "BUY above $" (the breakout level).
  - Horizontal line at the 10-day low labeled "SELL below $" (the exit if held).

Strategy: Donchian 20/10
  - 20-day high channel (entry).
  - 10-day low channel (exit).
  - Annotated entry / exit events across the displayed window.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import vcp_scanner
import config

CHARTS_DIR = Path(__file__).resolve().parent.parent / "results" / "charts"


def _ensure_dir():
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# VCP chart
# --------------------------------------------------------------------------- #
def draw_vcp_chart(df: pd.DataFrame, ticker: str, info: dict,
                    lookback_bars: int = 120, forward_bars: int = 25,
                    out_path: Optional[Path] = None) -> Path:
    """
    Draw a VCP setup chart for the given ticker at the detected pivot.
    `info` = dict returned by detect_vcp (base_high, base_low, contractions, ...).
    """
    _ensure_dir()
    if out_path is None:
        # Derive pivot date from the dataframe if 'date' isn't in info
        pivot_date_str = info.get("date")
        if pivot_date_str is None:
            pivot_idx_for_date = info["pivot_idx"]
            # pivot_idx is end_idx-1 in detect_vcp terms; we want df.index[pivot_idx]
            try:
                pivot_date_str = df.index[pivot_idx_for_date].strftime("%Y-%m-%d")
            except Exception:
                pivot_date_str = "recent"
        out_path = CHARTS_DIR / f"{ticker}_VCP_{pivot_date_str}.png"

    end_idx = info["pivot_idx"] + 1  # detect_vcp uses end_idx-1 as pivot
    bs = max(0, info["base_high_idx"] - 10)
    # Show through TODAY (or whatever the latest bar in df is), not just pivot+forward.
    # This lets you see the post-pivot performance / outcome of the trade.
    be = len(df) - 1
    window = df.iloc[bs:be + 1].copy()

    # Pivot date (info may not have 'date' key when called directly from detector)
    pivot_date_str = info.get("date")
    if pivot_date_str is None:
        try:
            pivot_date_str = df.index[info["pivot_idx"]].strftime("%Y-%m-%d")
        except Exception:
            pivot_date_str = "recent"

    fig, (axp, axv) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1],
                                                  "hspace": 0.05})
    # Header label: LIVE (covers today's close) vs HISTORICAL (most recent setup)
    status = info.get("status", "HISTORICAL")
    if status == "LIVE":
        header_tag = "  [LIVE - valid as of today's close]"
        header_color = "green"
    else:
        days_ago = info.get("days_ago")
        header_tag = f"  [HISTORICAL - most recent setup: {pivot_date_str}, {days_ago}d ago]"
        header_color = "darkorange"
    axp.set_title(f"{ticker}  -  VCP setup  (pivot: {pivot_date_str}){header_tag}",
                   fontsize=13, fontweight="bold", color=header_color)

    # Price
    close_key = "Close" if "Close" in window.columns else window.columns[0]
    axp.plot(window.index, window[close_key], color="#1f77b4", linewidth=1.4)

    # Base band
    bh = info["base_high"]
    bl = info["base_low"]
    axp.axhline(bh, color="#d62728", linestyle="--", linewidth=1.4,
                 label=f"BASE HIGH = ${bh:.2f}  (BUY above)")
    axp.axhline(bl, color="#7f7f7f", linestyle=":", linewidth=1.0,
                 label=f"BASE LOW = ${bl:.2f}")

    # 10-day low as exit (trailing stop).
    # For HISTORICAL charts: use the 10-day low just BEFORE the pivot (so
    #   the post-pivot outcome box correctly shows whether the stop was hit).
    # For LIVE charts: use the 10-day low as of TODAY's close, since you'd be
    #   entering now and the current trailing stop is what matters.
    status = info.get("status", "HISTORICAL")
    low_series = df["Low"] if "Low" in df.columns else df["Close"]
    if status == "LIVE":
        last10_low = float(low_series.iloc[end_idx - 10:end_idx].min())
        exit_label = f"EXIT (current 10d low) if close < ${last10_low:.2f}"
    else:
        last10_low = float(low_series.iloc[end_idx - 10:end_idx].min())
        exit_label = f"EXIT (10d low at pivot) if close < ${last10_low:.2f}"
    # Bold green dash-dot, thicker so it's clearly visible alongside base lines.
    axp.axhline(last10_low, color="#2ca02c", linestyle="-.", linewidth=1.6,
                 label=exit_label)

    # Highlight the base span
    if info["base_high_idx"] >= bs and info["pivot_idx"] < be:
        span_start = df.index[info["base_high_idx"]]
        span_end = df.index[info["pivot_idx"]]
        axp.axvspan(span_start, span_end, color="#ffdd55", alpha=0.18)

    # Contraction markers
    for i, c in enumerate(info["contractions"], start=1):
        abs_idx = info["base_high_idx"] + c[0]
        if abs_idx < bs or abs_idx > be:
            continue
        d = df.index[abs_idx]
        axp.scatter([d], [c[2]], marker="v", s=85, color="#e377c2", zorder=5,
                     edgecolor="black", linewidth=0.5)
        axp.annotate(f"C{i}: drop {c[4]*100:.1f}%",
                      xy=(d, c[2]),
                      xytext=(8, 14), textcoords="offset points",
                      fontsize=9, color="#7e1f7e", fontweight="bold")

    # Pivot / breakout marker
    pivot_date = df.index[end_idx]
    axp.axvline(pivot_date, color="#2ca02c", linestyle="-.", linewidth=1.0, alpha=0.7,
                 label=f"Pivot {pivot_date.date()}")
    axp.scatter([pivot_date], [df[close_key].iloc[end_idx]],
                 marker="*", s=220, color="#2ca02c", zorder=6,
                 edgecolor="black", linewidth=0.6, label="Pivot (VCP date)")

    # Post-pivot outcome box: what would have happened if you bought the breakout
    breakout_price = bh  # buy at the breakout level
    final_close = float(df[close_key].iloc[be])
    final_date = df.index[be].strftime("%Y-%m-%d")
    pnl_pct = (final_close - breakout_price) / breakout_price * 100
    pnl_color = "#2ca02c" if pnl_pct >= 0 else "#d62728"
    # Did the trade hit the 10-day-low stop before today?
    exit_arrow = ""
    # Walk forward from pivot; check if any close broke below pivot-time 10-day low
    hit_stop = False
    stop_date = None
    for i in range(end_idx + 1, be + 1):
        c = float(df[close_key].iloc[i])
        if c < last10_low:
            hit_stop = True
            stop_date = df.index[i].strftime("%Y-%m-%d")
            break

    if hit_stop:
        exit_str = f"STOPPED OUT {stop_date} (close < ${last10_low:.2f})"
        pnl_str = f"Realized: {((last10_low - breakout_price)/breakout_price)*100:+.2f}%"
        pnl_color = "#d62728"
    else:
        exit_str = f"Still held as of {final_date}"
        pnl_str = f"Unrealized: {pnl_pct:+.2f}% (bought ${breakout_price:.2f}, now ${final_close:.2f})"

    # Annotation: BUY/SELL hints (top-right)
    axp.text(0.99, 0.97,
              f"BUY: close > ${bh:.2f} on volume > 1.5x avg\nSELL if close < ${last10_low:.2f} (10d low)\n{exit_str}\n{pnl_str}",
              transform=axp.transAxes, ha="right", va="top", fontsize=10,
              color=pnl_color,
              bbox=dict(facecolor="white", edgecolor=pnl_color, boxstyle="round,pad=0.4"))

    axp.grid(True, alpha=0.3)
    axp.set_ylabel("Price ($)")
    axp.legend(loc="upper left", fontsize=9, ncol=2)

    # Volume panel
    if "Volume" in window.columns:
        axv.bar(window.index, window["Volume"], color="#888888", alpha=0.5, width=1.0)
        # Average volume line for the base
        base_avg = df["Volume"].iloc[info["base_high_idx"]:info["pivot_idx"] + 1].mean()
        axv.axhline(base_avg, color="#ff7f0e", linestyle=":", linewidth=0.9,
                     label="base avg vol")
        axv.legend(loc="upper left", fontsize=8)
        axv.set_ylabel("Volume")
    axv.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Donchian 20/10 chart
# --------------------------------------------------------------------------- #
def draw_donchian_chart(df: pd.DataFrame, ticker: str,
                         entry_window: int = None, exit_window: int = None,
                         lookback_bars: int = 90, out_path: Optional[Path] = None) -> Path:
    """
    Draw a Donchian 20/10 chart with channels and any entry/exit events over the
    last `lookback_bars` days.
    """
    _ensure_dir()
    if entry_window is None:
        entry_window = config.ENTRY_WINDOW if hasattr(config, "ENTRY_WINDOW") else 20
    if exit_window is None:
        exit_window = config.EXIT_WINDOW if hasattr(config, "EXIT_WINDOW") else 10
    if out_path is None:
        last_date = df.index[-1].strftime("%Y-%m-%d")
        out_path = CHARTS_DIR / f"{ticker}_Donchian_{last_date}.png"

    end_idx = len(df) - 1
    bs = max(0, end_idx - lookback_bars)
    window = df.iloc[bs:end_idx + 1].copy()
    close = df["Close"].astype(float)
    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close

    # Compute channels across the full series so events are detectable
    entry_chan = high.rolling(entry_window).max().shift(1)  # max of last 20 days, excl today
    exit_chan = low.rolling(exit_window).min().shift(1)     # min of last 10 days, excl today

    # Detect entry/exit events in the displayed window
    events = []
    held = False
    for i in range(bs, end_idx + 1):
        e_lvl = entry_chan.iloc[i]
        x_lvl = exit_chan.iloc[i]
        if not np.isfinite(e_lvl) or not np.isfinite(x_lvl):
            continue
        c = close.iloc[i]
        h = high.iloc[i]
        l = low.iloc[i]
        d = df.index[i]
        if not held and h > e_lvl:
            events.append((d, "ENTRY", float(e_lvl), float(c)))
            held = True
        elif held and l < x_lvl:
            events.append((d, "EXIT", float(x_lvl), float(c)))
            held = False

    fig, (axp, axv) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1],
                                                  "hspace": 0.05})
    last_date = df.index[end_idx].strftime("%Y-%m-%d")
    axp.set_title(f"{ticker}  -  Donchian {entry_window}/{exit_window}  (as of {last_date})",
                   fontsize=13, fontweight="bold")

    axp.plot(window.index, window["Close"], color="#1f77b4", linewidth=1.4, label="Close")
    # Plot channels restricted to the window
    axp.plot(entry_chan.iloc[bs:end_idx + 1].index, entry_chan.iloc[bs:end_idx + 1].values,
              color="#d62728", linestyle="--", linewidth=1.0, label=f"Entry: {entry_window}d high")
    axp.plot(exit_chan.iloc[bs:end_idx + 1].index, exit_chan.iloc[bs:end_idx + 1].values,
              color="#2ca02c", linestyle=":", linewidth=1.0, label=f"Exit: {exit_window}d low")

    # Mark events in window
    entered = False
    for d, kind, lvl, c in events:
        if kind == "ENTRY":
            axp.scatter([d], [c], marker="^", s=130, color="#2ca02c", zorder=6,
                         edgecolor="black", linewidth=0.5)
            axp.annotate(f"BUY\n${lvl:.2f}", xy=(d, c),
                          xytext=(-10, 18), textcoords="offset points",
                          fontsize=8, color="#2ca02c", fontweight="bold", ha="left")
        else:
            axp.scatter([d], [c], marker="v", s=130, color="#d62728", zorder=6,
                         edgecolor="black", linewidth=0.5)
            axp.annotate(f"SELL\n${lvl:.2f}", xy=(d, c),
                          xytext=(-10, -28), textcoords="offset points",
                          fontsize=8, color="#d62728", fontweight="bold", ha="left")

    today_close = float(close.iloc[end_idx])
    today_entry = float(entry_chan.iloc[end_idx]) if np.isfinite(entry_chan.iloc[end_idx]) else float("nan")
    today_exit = float(exit_chan.iloc[end_idx]) if np.isfinite(exit_chan.iloc[end_idx]) else float("nan")
    today_date = df.index[end_idx].strftime("%Y-%m-%d")
    axp.text(0.99, 0.97,
              f"As of {today_date}: Close ${today_close:.2f}\n"
              f"BUY if close > {entry_window}d high = ${today_entry:.2f}\n"
              f"SELL if close < {exit_window}d low = ${today_exit:.2f}",
              transform=axp.transAxes, ha="right", va="top", fontsize=10,
              bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.4"))

    axp.grid(True, alpha=0.3)
    axp.set_ylabel("Price ($)")
    axp.legend(loc="upper left", fontsize=9)

    if "Volume" in window.columns:
        axv.bar(window.index, window["Volume"], color="#888888", alpha=0.5, width=1.0)
        axv.set_ylabel("Volume")
        axv.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# 20-MA Trend chart (STRONG-ABOVE or BLOCKED-BY-MA)
# --------------------------------------------------------------------------- #
def draw_ma_trend_chart(df: pd.DataFrame, ticker: str, signal,
                         lookback_bars: int = 120,
                         out_path: Optional[Path] = None) -> Path:
    """
    Draw a 20-MA trend-strength chart showing:
      - Close price
      - SMA-20 line
      - Above-MA region shaded green (STRONG-ABOVE) or below-MA shaded red (BLOCKED)
      - Rejection markers (where price tested MA and was rejected)
      - A status box: regime, days above/below, % above MA, rejections
    """
    import ma_trend_scanner as mat
    _ensure_dir()
    if out_path is None:
        out_path = CHARTS_DIR / f"{ticker}_MA20_{signal.regime}_{signal.date}.png"

    end_idx = len(df) - 1
    bs = max(0, end_idx - lookback_bars)
    window = df.iloc[bs:end_idx + 1].copy()
    close = df["Close"].astype(float)
    ma = close.rolling(mat.MA_WINDOW).mean()
    close_key = "Close"

    fig, (axp, axv) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1],
                                                  "hspace": 0.05})

    regime = signal.regime
    regime_color = "#2ca02c" if regime == "STRONG-ABOVE" else "#d62728"
    regime_emoji = "+" if regime == "STRONG-ABOVE" else "-"
    title = (f"{ticker}  -  20-MA Trend  [{regime_emoji} {regime}]  "
             f"({signal.date}, {signal.window_days}d window)")
    axp.set_title(title, fontsize=13, fontweight="bold", color=regime_color)

    axp.plot(window.index, window[close_key], color="#1f77b4", linewidth=1.4, label="Close")
    win_ma = ma.iloc[bs:end_idx + 1]
    axp.plot(win_ma.index, win_ma.values, color="#ff7f0e", linewidth=1.6,
              label=f"SMA-{mat.MA_WINDOW}")

    # Shade the above/below regions
    target_mask = window[close_key] > win_ma if regime == "STRONG-ABOVE" else window[close_key] < win_ma
    in_run = False
    run_start = None
    for i, (d, a) in enumerate(zip(window.index, target_mask)):
        if a and not in_run:
            in_run = True
            run_start = d
        elif not a and in_run:
            in_run = False
            axp.axvspan(run_start, d, color=regime_color, alpha=0.12)
    if in_run:
        axp.axvspan(run_start, window.index[-1], color=regime_color, alpha=0.12)

    # Mark rejection events
    n = len(window)
    for i in range(1, n - 1):
        c = float(window[close_key].iloc[i])
        m = float(win_ma.iloc[i])
        if not np.isfinite(m) or m <= 0:
            continue
        if (c >= m * (1 - mat.REJECTION_TOLERANCE) and c <= m * (1 + mat.REJECTION_TOLERANCE)):
            for j in range(i + 1, min(i + 4, n)):
                if float(window[close_key].iloc[j]) < float(win_ma.iloc[j]):
                    d = window.index[i]
                    axp.scatter([d], [c], marker="x", s=100, color="red",
                                  zorder=6, linewidths=2)
                    axp.annotate(" rejection", xy=(d, c),
                                  xytext=(4, 8), textcoords="offset points",
                                  fontsize=8, color="red")
                    break

    tag_str = (f"Regime     : {regime}\n"
                f"Close      : ${signal.close:.2f}\n"
                f"MA-{mat.MA_WINDOW}     : ${signal.ma20:.2f}\n"
                f"% above MA : {signal.pct_above_ma:+.2f}%\n"
                f"Days above : {signal.days_above_in_window}/{signal.window_days}\n"
                f"Days below : {signal.days_below_in_window}/{signal.window_days}\n"
                f"Rejections : {signal.rejections_in_window}")
    axp.text(0.99, 0.97 if regime == "STRONG-ABOVE" else 0.03,
              tag_str,
              transform=axp.transAxes, ha="right",
              va="top" if regime == "STRONG-ABOVE" else "bottom",
              fontsize=10, color=regime_color,
              bbox=dict(facecolor="white", edgecolor=regime_color,
                         boxstyle="round,pad=0.4"))

    axp.grid(True, alpha=0.3)
    axp.set_ylabel("Price ($)")
    axp.legend(loc="upper left", fontsize=9)

    if "Volume" in window.columns:
        axv.bar(window.index, window["Volume"], color="#888888", alpha=0.5, width=1.0)
        axv.set_ylabel("Volume")
        axv.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
