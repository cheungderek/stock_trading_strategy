"""
scan_menu.py - unified CLI runner that lets the user pick the strategy, then
fetches data, scans the watchlist, sends a Facebook Messenger alert via
CallMeBot, and generates annotated PNG charts showing the buy/sell points.

Usage:
  python3 src/scan_menu.py            # interactive menu
  python3 src/scan_menu.py 1          # option 1 - VCP
  python3 src/scan_menu.py 2          # option 2 - Donchian
  python3 src/scan_menu.py 3          # option 3 - both
  python3 src/scan_menu.py --dry-run 1
  python3 src/scan_menu.py --test-alert
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import config
import data
import scanner
import vcp_scanner
import notifier
import chart_marker
import ma_trend_scanner
import strategy_selector as sel


def _setup_logging():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


def fetch_watchlist(force_refresh: bool = True, end_date: str = None) -> dict:
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    # Fetch ~2 years of history so 200-day SMA + VCP base detection both work
    start = (datetime.now() - timedelta(days=800 + config.LOOKBACK_BARS * 2)).strftime("%Y-%m-%d")
    df_dict = data.fetch_universe(
        start=start, end=end, tickers=config.WATCHLIST, quiet=False,
        min_bars=50, force=force_refresh,
    )
    return df_dict


def run_donchian(df_dict: dict, dry_run: bool, log) -> dict:
    """Run the Donchian 20/10 scanner + draw charts for any ticker with signals."""
    signals = scanner.scan_watchlist(df_dict)
    summary = scanner.signal_summary_text(signals)
    log.info("\n%s\n", summary)

    # Draw charts for the tickers with ENTRY signals today
    charts_made = []
    for ticker, sigs in signals.items():
        if not any(s.type == "ENTRY" for s in sigs):
            continue
        if ticker not in df_dict:
            continue
        try:
            path = chart_marker.draw_donchian_chart(df_dict[ticker], ticker)
            charts_made.append(path)
            log.info("Donchian chart saved: %s", path)
        except Exception as e:
            log.warning("Failed drawing Donchian chart for %s: %s", ticker, e)
    return {"signals": signals, "summary": summary, "charts": charts_made}


def run_ma_trend(df_dict: dict, dry_run: bool, log) -> dict:
    """Run the 20-MA Trend scanner: find stocks consistently above their 20-MA
    (STRONG-ABOVE) and stocks consistently rejected at their 20-MA (BLOCKED-BY-MA).
    Draws one annotated chart per detected ticker."""
    signals = ma_trend_scanner.scan_watchlist_ma_trend(df_dict)
    summary = ma_trend_scanner.ma_trend_summary(signals)
    log.info("\n%s\n", summary)

    charts_made = []
    for ticker, sig in signals.items():
        if ticker not in df_dict:
            continue
        try:
            path = chart_marker.draw_ma_trend_chart(df_dict[ticker], ticker, sig)
            charts_made.append(path)
            log.info("MA20 chart (%s): %s", sig.regime, path)
        except Exception as e:
            log.warning("Failed drawing MA20 chart for %s: %s", ticker, e)
    return {"signals": signals, "summary": summary, "charts": charts_made}


def run_vcp(df_dict: dict, dry_run: bool, log) -> dict:
    """
    Run VCP detector in three modes:
      1. LIVE       - which tickers satisfy all 7 VCP criteria AS OF TODAY'S close
                      (the yellow band ends at today; you can put a buy stop above base_high)
      2. FORMING    - which tickers are structurally building toward a VCP (relaxed
                      criteria, watch list for upcoming breakouts).
      3. LIVE EXITS - for any open VCP position tracked in results/vcp_positions.json
                      (i.e. tickers that fired LIVE entries on prior scans), check
                      today's close against the trailing 10-day-low stop. Emits
                      EXIT alerts when the stop is hit. Also registers today's
                      LIVE entries as new positions for future exit tracking.
      4. MOST RECENT HISTORICAL - for each ticker, the most recent VCP setup in
                      the last 250 trading days (chart shows pivot + outcome).

    Charts are produced for LIVE, FORMING, and the most recent historical setups.
    """
    live_signals = vcp_scanner.scan_watchlist_vcp(df_dict)
    forming_signals = vcp_scanner.scan_watchlist_vcp_forming(df_dict)
    hist_signals = vcp_scanner.scan_watchlist_vcp_historical(df_dict, lookback_days=250)

    # Live exit tracking (depends on today's LIVE entries to register them)
    exits, opened, open_positions = vcp_scanner.scan_watchlist_vcp_exits(
        df_dict, live_entries=live_signals)

    live_summary = vcp_scanner.vcp_signal_summary(live_signals)
    forming_summary = vcp_scanner.vcp_forming_summary(forming_signals)
    exit_summary = vcp_scanner.vcp_exit_summary(exits)
    hist_summary = vcp_scanner.vcp_historical_summary(hist_signals)
    combined = "\n\n".join([live_summary, forming_summary, exit_summary, hist_summary])
    log.info("\n%s\n", combined)

    # Charts: draw for every ticker that has a LIVE, FORMING or HISTORICAL setup.
    # LIVE preferred, then FORMING (augment with forming info), then HIST.
    charts_made = []
    chart_keys = {}

    # First news: every ticker with a most-recent HIST setup (covers all of them).
    for ticker, info in hist_signals.items():
        chart_keys[ticker] = ("HIST", info)

    # Override with FORMING (we want a watch-list chart, even if HIST is older).
    for ticker, info in forming_signals.items():
        chart_keys[ticker] = ("FORMING", info)

    # LIVE overrides everything (we want today's actionable chart).
    for ticker, info in live_signals.items():
        chart_keys[ticker] = ("LIVE", info)

    # Issue charts (cap to 12 most recent / actionable to avoid spam).
    # Sort: LIVE first (highest priority), then FORMING, then HISTORICAL (most recent first).
    def chart_sort_key(item):
        tag, _ = item[1]
        order = {"LIVE": 0, "FORMING": 1, "HIST": 2}.get(tag, 9)
        days_ago = item[1][1].get("days_ago", 0 if tag != "HIST" else 9999)
        return (order, days_ago)
    sorted_keys = sorted(chart_keys.items(), key=chart_sort_key)[:12]

    for ticker, (tag, info) in sorted_keys:
        if ticker not in df_dict:
            continue
        try:
            path = chart_marker.draw_vcp_chart(df_dict[ticker], ticker, info)
            charts_made.append(path)
            log.info("VCP chart (%s): %s", tag, path)
        except Exception as e:
            log.warning("Failed drawing VCP chart for %s: %s", ticker, e)
    return {"live_signals": live_signals,
            "forming_signals": forming_signals,
            "exits": exits,
            "opened_positions": opened,
            "open_positions": open_positions,
            "hist_signals": hist_signals,
            "summary": combined, "charts": charts_made}


def main():
    _setup_logging()
    log = logging.getLogger("scan_menu")

    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", nargs="?", default=None,
                    help="1=VCP, 2=Donchian, 3=both (if omitted, interactive menu)")
    ap.add_argument("--dry-run", action="store_true", help="Don't send FB Messenger alerts")
    ap.add_argument("--test-alert", action="store_true")
    ap.add_argument("--no-refresh", action="store_true",
                    help="Use cached CSVs (faster, may be stale)")
    ap.add_argument("--open-charts", action="store_true",
                    help="Open any generated charts in Preview after run")
    args = ap.parse_args()

    log.info("=" * 70)
    log.info("Strategy scanner starting at %s", datetime.now().isoformat())

    if args.test_alert:
        msg = "✅ Strategy scanner test alert (VCP + Donchian) — pipeline is working."
        try:
            resp = notifier.send(msg)
            log.info("Test alert sent. Response: %s", resp)
        except Exception as e:
            log.error("Test alert failed: %s", e)
        return

    # Strategy selection
    strategy = sel.prompt(args.strategy)
    log.info("Selected strategy: %s", strategy)

    # Fetch
    df_dict = fetch_watchlist(force_refresh=not args.no_refresh)
    if not df_dict:
        log.error("No data downloaded. Aborting.")
        sys.exit(1)
    log.info("Got data for %d / %d watchlist tickers", len(df_dict), len(config.WATCHLIST))
    latest_dates = [str(d.index[-1].date()) for d in df_dict.values() if len(d)]
    if latest_dates:
        log.info("Most recent data date across tickers: %s", max(latest_dates))

    # Run
    results = []
    if strategy == "vcp":
        results.append(("VCP", run_vcp(df_dict, args.dry_run, log)))
    elif strategy == "donchian":
        results.append(("Donchian", run_donchian(df_dict, args.dry_run, log)))
    elif strategy == "ma_trend":
        results.append(("MA20", run_ma_trend(df_dict, args.dry_run, log)))
    elif strategy == "both":
        results.append(("VCP", run_vcp(df_dict, args.dry_run, log)))
        results.append(("Donchian", run_donchian(df_dict, args.dry_run, log)))
    elif strategy == "all":
        results.append(("VCP", run_vcp(df_dict, args.dry_run, log)))
        results.append(("Donchian", run_donchian(df_dict, args.dry_run, log)))
        results.append(("MA20", run_ma_trend(df_dict, args.dry_run, log)))

    # Compose alert message
    parts = []
    any_signals = False
    all_charts = []
    for name, r in results:
        # VCP returns live/forming/hist signals plus live exits; Donchian returns signals
        if name == "VCP":
            # Treat LIVE entries, FORMING watch-list, and EXIT alerts as actionable.
            sigs = (r.get("live_signals")
                    or r.get("forming_signals")
                    or r.get("exits")
                    or r.get("hist_signals") or {})
            # Exits and new LIVE entries count as actionable even if hist is the only dict.
            if r.get("exits") or r.get("live_signals") or r.get("forming_signals"):
                any_signals = True
        else:
            sigs = r.get("signals") or {}
        if sigs:
            any_signals = True
        parts.append(r["summary"])
        all_charts.extend(r["charts"])

    combined = "\n---\n".join(parts)

    # Add chart list to the alert message
    if all_charts:
        chart_lines = "\n📉 Charts saved for:\n" + "\n".join(f"  {p.name}" for p in all_charts)
        combined += chart_lines

    if args.dry_run:
        log.info("Dry-run: not sending alerts.")
        if args.open_charts and all_charts:
            for p in all_charts:
                webbrowser.open(f"file://{p}")
        return

    # Decide whether to send heartbeat / alert
    send = any_signals or config.SEND_HEARTBEAT
    msg_to_send = combined if any_signals else (
        f"✅ Scanner ran {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
        f"Strategy: '{strategy}'. No new signals. Latest data: "
        f"{max(latest_dates) if latest_dates else '?'}."
    )

    if not send:
        log.info("No signals; no notification sent.")
        if all_charts:
            log.info("Charts saved at: %s", CHARTS_DIR := chart_marker.CHARTS_DIR)
        return

    try:
        # CallMeBot has a ~1 message / 10 sec rate-limit; message may be long,
        # so split if very large. For simplicity we send as one message.
        resp = notifier.send(msg_to_send)
        log.info("Alert sent via CallMeBot. Response: %s", resp)
    except Exception as e:
        log.error("Alert failed: %s", e)
        sys.exit(1)

    if args.open_charts and all_charts:
        for p in all_charts:
            webbrowser.open(f"file://{p}")


if __name__ == "__main__":
    main()
