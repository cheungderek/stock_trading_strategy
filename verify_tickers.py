"""Verify which tickers resolve on yfinance and basic data availability."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import yfinance as yf

raw = "T, TEM, TSLA, TSM, TXN, UBER, UNH, VZ, WMT, XIACF, NOK, MA, META, MRVL, MSFT, MU, NVDA, PDD, PLTR, RBLX, SPCX, SKHY, INTC, GOOGL, GLD, HSBC, JD, JPM, KO, CIEN, COST, BRK.BAMD, AMZN, ARM, ASML, BA, BABA"
tickers = [t.strip() for t in raw.split(",") if t.strip()]
print(f"Verifying {len(tickers)} tickers ...\n")
results = []
for t in tickers:
    try:
        d = yf.download(t, period="5d", progress=False, auto_adjust=True, multi_level_index=False)
        if d is None or d.empty:
            results.append((t, "NO DATA"))
        else:
            results.append((t, f"OK ({len(d)} bars, last={d['Close'].iloc[-1]:.2f})"))
    except Exception as e:
        results.append((t, f"ERR: {e}"))
    time.sleep(0.1)

print(f"{'Ticker':<10} {'Status'}")
print("-" * 50)
for t, s in results:
    print(f"{t:<10} {s}")
