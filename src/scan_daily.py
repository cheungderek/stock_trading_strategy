"""
scan_daily.py - daily Donchian 20/10 breakout scanner.

Usage:
  python3 src/scan_daily.py                # scan today, send alerts
  python3 src/scan_daily.py --dry-run      # scan today, print only
  python3 src/scan_daily.py --test-alert    # send a test message to verify pipeline

Runs on the watchlist in src/config.py. Download is done via the shared data.py
cache (CSV files in data/), refreshed if older than DATA_REFRESH_HOURS.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import config
import data
import scanner
import notifier


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


def fetch_watchlist_data(end_date: str = None, force_refresh: bool = True) -> dict:
    """Download daily bars for all watchlist tickers.
    Default: force_refresh=True so we always pull the latest data from yfinance
    rather than serving stale cache (cache TTL is too lenient for a daily scanner).
    """
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    # Need ENTRY_WINDOW+ATR plus margin: ~80 bars
    start = (datetime.now() - timedelta(days=2 * (config.LOOKBACK_BARS + 30))).strftime("%Y-%m-%d")
    df_dict = data.fetch_universe(
        start=start, end=end, tickers=config.WATCHLIST, quiet=False, min_bars=50,
        force=force_refresh,
    )
    return df_dict


def main():
    _setup_logging()
    log = logging.getLogger("scan_daily")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Don't send alerts, just print")
    ap.add_argument("--test-alert", action="store_true", help="Send a test FB Messenger alert then exit")
    ap.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--no-refresh", action="store_true",
                    help="Use cached CSVs instead of re-downloading (faster, may be stale)")
    args = ap.parse_args()

    log.info("=" * 70)
    log.info("Donchian 20/10 daily scan starting at %s", datetime.now().isoformat())

    # --- Test pipeline only ---
    if args.test_alert:
        msg = (
            "✅ Donchian scanner test alert — pipeline is working.\n"
            "If you received this message, CallMeBot + FB Messenger are wired up correctly."
        )
        log.info("Sending test alert via CallMeBot ...")
        try:
            resp = notifier.send(msg)
            log.info("Test alert sent. Response: %s", resp)
        except Exception as e:
            log.error("Test alert failed: %s", e)
            sys.exit(1)
        return

    # --- Normal scan ---
    df_dict = fetch_watchlist_data(end_date=args.end, force_refresh=not args.no_refresh)
    if not df_dict:
        log.error("No data downloaded. Aborting.")
        sys.exit(1)
    log.info("Got data for %d / %d watchlist tickers", len(df_dict), len(config.WATCHLIST))

    # Sanity: log the latest data date seen across all tickers
    latest_dates = [str(d.index[-1].date()) for d in df_dict.values() if len(d)]
    if latest_dates:
        log.info("Most recent data date across tickers: %s", max(latest_dates))

    # Scan
    signals = scanner.scan_watchlist(df_dict)
    summary_text = scanner.signal_summary_text(signals)

    log.info("\n%s\n", summary_text)

    if args.dry_run:
        log.info("Dry-run: not sending alerts.")
        return

    # Send alert if there are signals, OR if heartbeat is enabled (so you know
    # the scanner is alive even on quiet days), OR if ALWAYS_SEND_TEST_ALERT is on.
    n_total = sum(len(v) for v in signals.values())
    send = False
    msg_to_send = summary_text
    if n_total > 0:
        send = True
    elif config.SEND_HEARTBEAT:
        send = True
        # Compact heartbeat message including the freshest data date we saw.
        latest = max(latest_dates) if latest_dates else "?"
        msg_to_send = (
            f"✅ Donchian scanner ran {datetime.now().strftime('%Y-%m-%d %H:%M')} "
            f"ET. No new signals. Latest data: {latest}."
        )
    elif config.ALWAYS_SEND_TEST_ALERT:
        send = True
        msg_to_send = f"ℹ️ Donchian scanner ran on {datetime.now().date()}. No new signals today."

    if not send:
        log.info("No signals; no notification sent.")
        return

    try:
        resp = notifier.send(msg_to_send)
        log.info("Alert sent via CallMeBot. Response: %s", resp)
    except Exception as e:
        log.error("Alert failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
