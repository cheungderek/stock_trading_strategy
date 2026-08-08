# Donchian 20/10 Breakout Scanner — US & Canadian Watchlist

A daily scanner that runs the **Donchian 20/10 breakout strategy** (Turtle-style
channel breakout — empirically the best of 10 candidate strategies we tested
on US + Canadian daily data) across your watchlist and fires Facebook Messenger
alerts via CallMeBot whenever a watchlist ticker triggers a fresh entry or exit
signal.

> You review each alert and decide whether to actually buy or sell. The
> scanner never places orders — it just tells you when something is happening.

---

## 1. What it does

- Downloads daily bars for your 38 watchlist tickers via yfinance.
- Runs the Donchian 20/10 breakout rule on each:
  - **ENTRY signal**: today's high broke the prior 20-day high (new long candidate)
  - **EXIT signal**:  today's low broke the prior 10-day low (sell candidate if held)
- Sends a Facebook Messenger message listing any new signals (one per ticker per
  day — duplicate alerts are suppressed via `results/scan_state.json`).
- Runs automatically every Mon–Fri at **5:30 PM ET** via a macOS LaunchAgent
  (about 30 minutes after the US market close, giving data providers time to
  settle EOD prices).

---

## 2. Why Donchian 20/10?

We compared six published, robust strategies on 2015–2024 daily data
(`src/run_all.py`):

| Strategy | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|
| **S5 Donchian 20/10 ✅** | **7.5%** | **9.0%** | **0.84** | -10% |
| S8 Turn-of-month | 4.9% | 6.3% | 0.78 | -9% |
| S10 Sector rotation | 3.8% | 5.5% | 0.70 | -8% |
| S1 TSMOM | 2.0% | 3.1% | 0.65 | -7% |
| S7 Halloween | 7.1% | 12.4% | 0.61 | -35% |
| S9 Risk parity | 1.2% | 4.0% | 0.32 | -12% |
| BENCH SPY | 13.1% | 17.5% | 0.78 | -34% |

Donchian had the **best risk-adjusted return (Sharpe = 0.84)** and the smallest
drawdown of any non-cash strategy. It also produces the most actionable alerts:
each signal gives an exact breakout level + exact stop level.

Full analysis: see `STRATEGIES.md`.

---

## 3. Project layout

```
stock_trading_strategy/
├── src/
│   ├── config.py         # watchlist + CallMeBot API key — edit this
│   ├── scanner.py        # Donchian 20/10 signal detection
│   ├── notifier.py       # CallMeBot FB Messenger sender
│   ├── scan_daily.py     # CLI entry point (fetch → scan → alert)
│   ├── data.py           # yfinance fetcher with CSV cache (data/)
│   ├── metrics.py        # CAGR, Sharpe, max DD, etc.
│   ├── engine.py         # backtest engine
│   ├── strategies.py     # all 6 survivor strategy implementations
│   └── run_all.py        # 6-strategy comparison backtest
├── data/                 # cached ticker CSV files
├── results/
│   ├── metrics.csv       # 6-strategy comparison
│   ├── returns.csv       # daily returns of each strategy
│   ├── equity_curve.png  # side-by-side equity curve
│   ├── scan_state.json   # scanner dedup state (don't delete)
│   ├── scanner.log       # running scanner log
│   ├── launchd_stdout.log
│   └── launchd_stderr.log
├── com.derekc.donchian-scanner.plist   # macOS LaunchAgent template
├── install_scheduler.py                 # install/uninstall the agent
├── verify_tickers.py                    # check watchlist resolves on yfinance
└── STRATEGIES.md                        # 10-strategy writeup
```

---

## 4. Setup

### 4.1 Dependencies

You need Python 3.10+ with `yfinance`, `pandas`, `numpy`, `matplotlib`. They're
already installed on this machine (`/opt/homebrew/bin/python3`).

### 4.2 CallMeBot + Facebook Messenger (one time)

1. Open Facebook Messenger on your phone or desktop.
2. Message the CallMeBot Facebook page with:
   ```
   I allow callmebot to send me messages
   ```
3. CallMeBot replies with an API key. Paste it into `src/config.py`:
   ```python
   CALLMEBOT_API_KEY = "your-key-here"
   ```
4. Send a test alert:
   ```bash
   python3 src/scan_daily.py --test-alert
   ```
   You should receive a "✅ Donchian scanner test alert ..." message in FB Messenger.

### 4.3 Watchlist

Edit `src/config.py`:
```python
WATCHLIST = ["AAPL", "MSFT", ..., "SHOP.TO", ...]  # use .TO for TSX tickers
```

Verify your tickers resolve on yfinance:
```bash
python3 verify_tickers.py
```

### 4.4 Install the daily auto-scan (macOS LaunchAgent)

```bash
python3 install_scheduler.py install
```

This installs `~/Library/LaunchAgents/com.derekc.donchian-scanner.plist` which
fires the scanner **every Mon–Fri at 5:30 PM local ET**.

Other commands:
```bash
python3 install_scheduler.py status      # show install + load status
python3 install_scheduler.py test        # run the scanner now (foreground)
python3 install_scheduler.py uninstall  # stop and remove the agent
```

Notes:
- The Mac must be on (not asleep) at 5:30 PM ET. If it's asleep, launchd will
  run the job once when it next wakes.
- If you shut down the Mac at 5:30 PM, that scan is skipped.

---

## 5. Daily usage

The scheduler is fully automatic. For manual runs, use the strategy menu
(`src/scan_menu.py`) — it lets you pick between VCP, Donchian 20/10, and the
20-MA Trend strategy:

```bash
# Interactive menu (pick a strategy each time)
python3 src/scan_menu.py

# Run a specific strategy directly:
python3 src/scan_menu.py 1     # VCP (Minervini)
python3 src/scan_menu.py 2     # Donchian 20/10 breakout
python3 src/scan_menu.py 3     # VCP + Donchian side-by-side
python3 src/scan_menu.py 4     # 20-MA Trend strength (STRONG-ABOVE / BLOCKED-BY-MA)
python3 src/scan_menu.py 5     # All three strategies in one run

# Common flags (combine with any strategy above):
python3 src/scan_menu.py --dry-run 1         # scan + print + draw charts, NO FB alert
python3 src/scan_menu.py --no-refresh 1      # use cached CSVs (faster, may be stale)
python3 src/scan_menu.py --open-charts 1     # open the generated PNGs in Preview after run
python3 src/scan_menu.py --test-alert        # send a single test FB Messenger message
```

The legacy Donchian-only entry point is still available (used by the
LaunchAgent scheduler):

```bash
# Donchian 20/10 only - run now and send a real alert if any new signals fire
python3 src/scan_daily.py

# Run but only print to console (no FB Messenger message)
python3 src/scan_daily.py --dry-run

# Send a single test message
python3 src/scan_daily.py --test-alert

# Run as-of a specific date (e.g. backfill last Friday's signals)
python3 src/scan_daily.py --end 2026-08-01
```

### What each strategy reports

| Opt | Strategy | Looks for |
|---|---|---|
| 1 | **VCP** | Minervini Volatility Contraction setups — LIVE (all 7 criteria today), FORMING (building toward a VCP, watch-list), and LIVE EXITS (open VCP positions hitting their 10-day-low stop). Historical most-recent setups also charted for context. |
| 2 | **Donchian 20/10** | New 20-day-high breakouts (ENTRY) and 10-day-low breaks (EXIT). |
| 4 | **20-MA Trend** | STRONG-ABOVE (close consistently above 20-MA, trend support) and BLOCKED-BY-MA (20-MA acting as overhead resistance). |

### Output files

- Charts: `results/charts/`  (one annotated PNG per detected ticker)
- Log: `results/scanner.log`
- Donchian dedup state: `results/scan_state.json` (delete to re-fire past signals)
- VCP open positions: `results/vcp_positions.json` (auto-maintained by the EXIT tracker; delete to reset)

---

## 6. What an alert looks like

```
📊 DONCHIAN 20/10 SCAN — 5 new signal(s)

🟢 ENTRY  MSFT  (2026-08-03)
  Close $487.65  vs 20d high $466.84
  Stop exit if close < 10d low
  ATR~1.9% of price (size ≈ 52% of equity per 1% risk)

🟢 ENTRY  AMZN  (2026-08-03)
  Close $284.02  vs 20d high $273.23
  Stop exit if close < 10d low
  ATR~1.94% of price (size ≈ 52% of equity per 1% risk)
...
```

For each ticker you get:
- Ticker + signal date
- Entry/breakout level (the 20-day high you broke)
- Exit rule (sell if close makes a new 10-day low)
- ATR-based suggested position size (so 1 ATR move = 1% of equity if you risk 1%)

You then double-check the chart, news, broader market context, and place an
order manually if it fits your conviction.

---

## 7. Strategy parameters (defaults, conventional Turtle values)

| Param | Value | Meaning |
|---|---|---|
| `ENTRY_WINDOW` | 20 days | buy new 20-day high |
| `EXIT_WINDOW` | 10 days | exit on new 10-day low |
| `RISK_PER_TRADE` | 1% | % of equity risked per trade |
| `ATR_WINDOW` | 20 days | for size calculation |
| `MAX_POSITIONS` | 12 | cap concurrent longs |

Edit `src/config.py` to change any of them.

---

## 8. Backtesting (for reference / sanity check)

Re-run the full 6-strategy comparison any time:

```bash
python3 src/run_all.py --start 2015-01-01 --end 2024-12-31
```

Outputs:
- `results/metrics.csv`
- `results/returns.csv`
- `results/equity_curve.png`

Live scanner is **separate from backtester**: scanner only uses the Donchian
rule on the watchlist; backtester evaluates all 6 strategies on a broad ETF
universe.

---

## 9. Troubleshooting

**No Facebook Messenger message arrives**
- Confirm `CALLMEBOT_API_KEY` is correct in `src/config.py`.
- Send `--test-alert` and watch the log: `tail -f results/scanner.log`.
- CallMeBot free tier has a rate limit (~1 message per ~10 sec); if you scan
  too frequently messages may queue.

**You got only one message on day one and nothing after — even though scheduler
shows LOADED and LastExitStatus = 0**
  This is the most common symptom and means the scanner **ran but found no NEW
  signals**, so by default it stayed silent. Two root causes (now both fixed):

  1. *Stale cached data* — the previous build would re-use `data/<ticker>.csv`
     files that were < 24 h old even if they didn't include today's bar. So the
     scanner kept reporting yesterday's signals, all of which were already in
     `results/scan_state.json` (duplicate-suppression file).
     **Fix applied:** `scan_daily.py` now forces a yfinance refresh on every run.
     You can also delete all cache files with `rm data/*.csv` and re-run.

  2. *Silent no-signal days* — the previous build only messaged you when there
     were signals, so a quiet day looked like the scanner was dead.
     **Fix applied:** a heartbeat flag was added. When no signals fire you
     still get a short "✅ Donchian scanner ran YYYY-MM-DD HH:MM ET. No new
     signals. Latest data: …" message. To turn the heartbeat off, set
     `SEND_HEARTBEAT = False` in `src/config.py`.

**launchd didn't fire at 5:30 PM ET**
- Check `python3 install_scheduler.py status` reports LOADED.
- Check `results/launchd_stderr.log` for errors.
- If the Mac was asleep, launchd runs the job once on wake but won't catch up
  multiple missed runs.
- You can always force a run: `python3 install_scheduler.py test`.

**A ticker only has a few bars / gets skipped**
- New IPOs or SIMPs need ≥50 trading days of history to satisfy the Donchian
  minimum window. SPCX and SKHY are currently in this bucket.
- Delete that ticker's stale `data/<TICKER>.csv` cache if it's out-of-date.

**Want to re-fire an alert I already saw**
- Delete the matching entry in `results/scan_state.json` (or delete the whole
  file to reset all dedup memory) and re-run.

**Verify the scanner sees fresh data**
- The log line "Most recent data date across tickers: YYYY-MM-DD" tells you the
  freshest bar the scanner actually used. It should be today (or the prior
  trading day if before market close). If it's stale, force refresh:
  `rm data/*.csv && python3 src/scan_daily.py`

---

## 10. Disclaimer

This is an educational tool. The Donchian 20/10 rule is a published, classical
strategy but Past performance is no guarantee of future returns. The scanner
emits signals — it does **not** place orders. Always review fundamentals, news,
and broader market context before trading.
