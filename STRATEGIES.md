# 10 Candidate Trading Strategies — US & Canadian Markets

**Compiled:** 2026-08-03
**Scope:** Daily-rebalance candidate strategies for the US and Canadian markets
**Selection criteria:** Old, simple, published ideas — no machine learning, no indicator mashups.

Strategies span five families: trend, mean reversion, breakout, seasonal, and position sizing.

---

## S1. Time-Series Momentum (TSMOM) — Trend

- **Rule (one line):** Hold long any asset whose past-12-month return is positive; short (or flat, long-only) if negative; rebalance monthly.
- **Why it pays:** Trend-followers ride slow under-reaction to fundamentals and risk-premium shifts. The edge comes from riding sustained price moves rather than fighting them.
- **Who loses & why they keep doing it:** Discretionary fundamental buyers who average down into downtrends because their DCF says "cheap." They keep doing it becausevaluation discipline is institutional religion.
- **Fits:** Broad liquid futures (stock index, FX, bonds, commodities) and ETF equivalents.
- **Doesn't fit:** Single micro-cap equities, illiquid names, anything with carry cost > expected move.
- **Published:** Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum," *Journal of Financial Economics*. Asness, Moskowitz & Pedersen (2013), "Value and Momentum Everywhere," *Journal of Financial Economics*.

---

## S2. Cross-Sectional Stock Momentum (Jegadeesh-Titman) — Trend

- **Rule (one line):** Long the top decile, short the bottom decile of 12-1 month past US stock returns; rebalance monthly.
- **Why it pays:** Investors anchor to news and under-extrapolate earnings drift. Losers capitulate and winners get added late, producing multi-quarter drift.
- **Who loses & why:** Late sellers of deteriorating names ("hold for recovery") and underweight latecomers to improving names. Behavior persists because anchor/disposition bias is structural.
- **Fits:** Large- and mid-cap US equities (NYSE/Nasdaq).
- **Doesn't fit:** Penny stocks, ultra-thin TSX-V names, recent IPOs (no 12-month history).
- **Published:** Jegadeesh & Titman (1993), "Returns to Buying Winners and Selling Losers," *Journal of Finance*. Carhart (1997), "On Persistence in Mutual Fund Performance," *Journal of Finance*.

---

## S3. Short-Term Reversal (1-Week) — Mean Reversion

- **Rule (one line):** Long bottom decile, short top decile of prior-1-week returns among large-cap stocks; rebalance weekly.
- **Why it pays:** Liquidity shocks (forced indexing, mutual-fund flow) push prices off fair value; price snaps back within a week.
- **Who loses & why:** Forced sellers (fund redemptions) and forced buyers (inflows), index-rebalance trackers. They keep happening becauseflow timing is institutional and unavoidable.
- **Fits:** High-turnover large-caps (S&P 100, TSX 60).
- **Doesn't fit:** Low-volume names, news-driven names where the move is informational.
- **Published:** Lehmann (1990), "Fads, Martingales and Efficiency," *NBER Working Paper*. Jegadeesh (1990), "Evidence of Predictable Behavior of Security Returns," *Review of Financial Studies*.

---

## S4. Opening-Range Breakout — Breakout

- **Rule (one line):** Buy if price breaks +X (e.g. 0.25% or 1 ATR-15min) above the first 30-min high; short symmetric; close at session close.
- **Why it pays:** Overnight accumulation of orders bursts out at the open; range breakouts mark the day's directional intent.
- **Who loses & why:** Range-fade / contrarian daytraders fading the break. They keep doing it because most days the range holds, so the strategy has high hit rate outside of trend days.
- **Fits:** Liquid index futures (ES, NQ, YM, TSX 60 futures), large-cap stocks with intraday volume.
- **Doesn't fit:** Illiquid TSX-V names, anything with a wide opening gap already.
- **Published:** Crabel, Toby (1990), *Day Trading with Short Term Price Patterns and Opening Range Breakout*. Raschke / Connors street-smarts literature.

---

## S5. Donchian-Channel Breakout (Turtle Rule) — Breakout

- **Rule (one line):** Buy new 20-day high (sell/short new 20-day low), exit on 10-day opposite extreme; one contract per trade; cap risk at ~2%.
- **Why it pays:** Captures regime shifts; small losses on false breaks, large wins on multi-month trends.
- **Who loses & why:** Mean-reverters who fade each new high. They keep fading because individually each high "looks" extended.
- **Fits:** Commodity futures, FX majors, index futures.
- **Doesn't fit:** Range-bound individual stocks, low-volume instruments where 20-day highs are random.
- **Published:** Richard Dennis / William Eckhardt "Turtle Traders" (1983). Covel, Michael (2007), *Trend Following*. Faith, Curtis (2007), *Way of the Turtle*.

---

## S6. January / Turn-of-the-Year Effect — Seasonal

- **Rule (one line):** Buy small-cap (or the bottom decile by market cap) US stocks in late December, sell in early February; long-only.
- **Why it pays:** Tax-loss selling depresses small caps in December; reinvested flows plus window dressing push them up in January.
- **Who loses & why:** Retail and forced institutional tax-loss sellers in December. Behavior persists because the tax code is permanent and window dressing is mandated.
- **Fits:** US small caps (Russell 2000 / decile-10 CRSP).
- **Doesn't fit:** Large caps; Canada (no analogous January seasonality in TSX; RRSP deadline effect is weaker).
- **Published:** Keim (1983), "Size-related Anomalies and Stock Return Seasonality," *Journal of Financial Economics*. Ritter (1988), "The Buying and Selling Behavior of Individual Investors at the Turn of the Year," *Journal of Finance*.

---

## S7. Sell in May / Halloween Effect — Seasonal

- **Rule (one line):** Hold the S&P 500 (and/or TSX Composite) November → April; switch to T-bills May → October.
- **Why it pays:** Vacation-induced lower risk appetite in summer; concentrated risk premia in winter.
- **Who loses & why:** Buy-and-hold investors who hold all year. Behavior persists because nobody's institutionally allowed to "sell in May."
- **Fits:** Seasonal mature markets (US, UK, Canada, Germany).
- **Doesn't fit:** Emerging markets; commodities that have their own seasonal calendar.
- **Published:** Bouman & Jacobsen (2002), "The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle," *American Economic Review*.

---

## S8. Turn-of-the-Month Effect — Seasonal

- **Rule (one line):** Be long the S&P 500 (or SPY) from the last trading day of the month through the 3rd trading day of the next month; flat otherwise.
- **Why it pays:** Payroll / 401(k) / RRSP / pension flows land on those days. Printed buying pressure at predictable dates.
- **Who loses & why:** Forced quarter-end sellers and passive balanced-fund rebalancers. They keep doing it because plan flows are scheduled, not chooseable.
- **Fits:** Broad index ETFs (SPY, IVV, XIC.TO in Canada).
- **Doesn't fit:** Individual stocks, commodities.
- **Published:** Lakonishok & Smidt (1988), "Are Seasonal Anomalies Real? A Ninety-Year Perspective," *Review of Financial Studies*. Ogden (1990), "Turn-of-the-Month Evaluations of Liquid Wealth and Stock Returns," *Journal of Financial Economics*.

---

## S9. Volatility Scaling / Risk Parity Position Sizing — Position Sizing

- **Rule (one line):** Size each asset so its volatility contribution is equal: weight_i = (1/sigma_i) / sum(1/sigma_j); rebalance monthly.
- **Why it pays:** Equal-vol bets diversify better than equal-dollar; Sharpe rises, drawdowns shrink. Not alpha — better risk allocation.
- **Who loses & why:** Equal-weight / cap-weight holders who over-allocate to high-beta assets. The "free lunch" of risk-balanced diversification comes from inside their inefficient allocation.
- **Fits:** Any multi-asset book (US + CA equities, bonds, gold, commodities).
- **Doesn't fit:** A single-name equity book, a one-asset portfolio.
- **Published:** Bridgewater All Weather (1996 onward). Maillard, Roncalli & Teiletche (2010), "The Properties of Equally Weighted Risk Contribution Portfolios," *Journal of Portfolio Management*.

---

## S10. Sector Rotation with Volatility Sizing — Trend + Position Sizing

- **Rule (one line):** Among a fixed basket of ~10 liquid ETFs (SPY, QQQ, IWM, XL? sectors, XIC.TO, XBB.TO), long only the top N by 6-month TSMOM ranking; weights inversely scaled by 20-day realized vol; rebalance monthly.
- **Why it pays:** Combines mild cross-sectional momentum with vol-target sizing — both well-documented edges, without the exposed short sleeve.
- **Who loses & why:** Static 60/40 holders who don't tilt toward the current leader. They sacrifice trend premium for "stability."
- **Fits:** ETF rotational portfolios in US + Canada.
- **Doesn't fit:** Individual stocks (cross-section too narrow).
- **Published:** Combination of Asness et al. (2013, TSMOM) and Meb Faber (2007), "A Quantitative Approach to Tactical Asset Allocation," *Journal of Wealth Management*. Wilkinson (2000) on sector rotation.

---

# Three-Check Grading

Every candidate is graded against three checks:

1. **(a) Is it old and published?** — pre-2013 literature, peer-reviewed or canonical trading book.
2. **(b) Is there a real reason it pays?** — identifiable losing counterparties doing something predictable.
3. **(c) Does it fit my market?** — applies to US + Canadian daily retail trading.

| # | Strategy | (a) Old & published | (b) Real reason it pays | (c) Fits US+CA daily | **Pass all 3?** |
|---|---|---|---|---|---|
| S1 | TSMOM | ✅ Moskowitz-Ooi-Pedersen 2012 | ✅ slow under-reaction + risk-premium shifts | ✅ via ETFs/futures | ✅ |
| S2 | Cross-sectional momentum (12-1) | ✅ Jegadeesh-Titman 1993 | ✅ under-extrapolation | ⚠️ Long-only-only short decile hard without borrow | ⚠️ short-leg impractical |
| S3 | 1-week reversal | ✅ Lehmann 1990 | ✅ liquidity shocks | ⚠️ Short leg + transaction costs | ⚠️ short leg + cost kills daily retail |
| S4 | Opening-range breakout | ✅ Crabel 1990 | ⚠️ Edge partly decayed (0DTE era) | ⚠️ intraday only, needs tick data | ⚠️ requires tick data |
| S5 | Donchian 20/10 | ✅ Eckhardt 1983 | ✅ regime shift | ✅ ETFs / futures | ✅ |
| S6 | January small-cap effect | ✅ Keim 1983 | ⚠️ Largely arbitraged post-1990 | ✅ but tiny effect now | ⚠️ decayed |
| S7 | Sell in May | ✅ Bouman-Jacobsen 2002 | ✅ vacation risk-aversion | ✅ broad indices | ✅ |
| S8 | Turn-of-month | ✅ Lakonishok-Smidt 1988 | ✅ scheduled inflows | ✅ SPY, XIC.TO | ✅ |
| S9 | Risk parity sizing | ✅ Maillard et al. 2010 | ✅ better diversification | ✅ any ETF book | ✅ |
| S10 | Sector rotation + vol sizing | ✅ Faber 2007 + TSMOM lit | ✅ trend + rotation + risk control | ✅ built for ETFs | ✅ |

**Survivors (pass all three cleanly):** **S1, S5, S7, S8, S9, S10** — six strategies.

### Why the four were rejected

- **S2** — short leg impractical at retail scale in US/CA for daily rebalance.
- **S3** — short leg + 1-week turnover kills post-commission.
- **S4** — requires intraday tick data; partially decayed since the rise of 0DTE options.
- **S6** — largely arbitraged; the residual January small-cap premium is too small to trade clean after costs.

---

# Concrete Rules for the 6 Survivors

Each rule below is precise enough to implement and backtest today with conventional parameter values. No fitting, no ML.

---

## S1 — TSMOM on a US+CA ETF / Futures Basket

- **Universe:** SPY, QQQ, IWM, DIA, XIC.TO (iShares TSX Capped Composite), XSP.TO (S&P 500 CAD-hedged), XBB.TO (CA gov bond ETF), GLD (gold), USO (oil), FXC (CAD/USD).
- **Rule:** On the last trading day of each month, compute each asset's total return over the prior 252 trading days (~12 months). Hold long any ETF with positive 12-month return; hold cash (BIL or cash.to) for any ETF with negative return. Equal dollar weights among held names.
- **Parameters:** 252-day lookback, monthly rebalance, 1bp commission assumption, slippage = 5bp.
- **Variant:** Long-only version (no shorts) — the default given borrow constraints.

---

## S5 — Donchian 20/10 Breakout on Liquid US+CA ETFs

- **Universe:** SPY, QQQ, IWM, XLK, XLF, XLE, VNQ, XIC.TO, XBB.TO (9-10 liquid ETFs).
- **Rule:** Buy market-on-open tomorrow if today's close made a new 20-trading-day high and the position is flat. Sell market-on-open if today's close made a new 10-trading-day low (long → flat). One position per ETF at a time. Risk 1% of equity per trade; position size = `(0.01 × equity) / (20-day ATR × ETF price × 100)` shares.
- **Parameters:** 20-day entry channel, 10-day exit channel, 1% risk/trade, stop = exit channel only (no fixed stop), cap 5 concurrent positions.

---

## S7 — Halloween / Sell-in-May on US & CA Indices

- **Universe:** SPY (US large-cap), XIC.TO (TSX Composite).
- **Rule:** Be long SPY and XIC.TO from the first trading day of November through the last trading day of April. Switch to BIL / cash.to (Canadian T-bills) May 1 → October 31.
- **Parameters:** 50/50 dollar weighting between SPY and XIC.TO during "in" months, 50/50 between BIL and cash.to during "out" months. Annual rebalances at Nov 1 and May 1. No leverage.
- **Known:** effect ~0.5–1.0%/yr above buy-and-hold; use as overlay, not standalone alpha.

---

## S8 — Turn-of-the-Month on SPY and XIC.TO

- **Universe:** SPY, XIC.TO.
- **Rule:** Be long SPY and/or XIC.TO from the close of the last trading day of month T through the close of the third trading day of month T+1; otherwise hold BIL / cash.to.
- **Parameters:** 100% allocation to the equity ETF during the 4-day window, 100% T-bill otherwise. Monthly. Equal vollar weighting between SPY and XIC.TO while in the window.
- **Note:** Measured edge ~0.3–0.6% of upside *during the 4 days* of each month; treat as a calendar overlay.

---

## S9 — Volatility-Scaling / Risk Parity Across US+CA Asset ETFs

- **Universe:** SPY (US equity), AGG (US bonds), VNQ (US REIT), GLD (gold), DBC (commodities), XIC.TO (CA equity), XBB.TO (CA bonds), FXC (CAD FX as currency-hedge proxy). (8 assets.)
- **Rule:** At each month-end, compute each asset's realized sigma from the last 60 trading days' log returns. Weight `w_i = (1/sigma_i) / sum(1/sigma_j)`. Total portfolio vol target = 10% annualized; if realized portfolio vol ≠ 10%, scale all weights by `10% / realized`.
- **Parameters:** 60-day sigma lookback, 10% vol target, monthly rebalance, gross exposure ≤ 100% (no leverage).

---

## S10 — Trend Rotation Across Sector ETFs (Long-Only, Vol-Targeted)

- **Universe (10 ETFs, fixed):** SPY, QQQ, IWM, XLK, XLF, XLE, XLV, XLI, XIC.TO, XBB.TO.
- **Rule:** At each month-end, rank ETFs by their 126-trading-day (~6-month) total return. Take a long position in the top 3; remaining 7 are flat (T-bills). Weight each held asset inversely to its trailing 20-day realized vol, so higher-vol names get smaller dollar weight. Total target portfolio vol = 15% annualized; rescale if needed.
- **Parameters:** 6-month ranking, top-3 hold, 20-day sigma for sizing, 15% vol target, monthly rebalance.
- **Edge drivers:** trend + concentrated active share + risk control, each component separately documented.

---

# Summary of Ready-to-Test Survivors

| # | Strategy | Rebalance | Lookback params | Edge source |
|---|---|---|---|---|
| S1 | TSMOM (US+CA ETF) | Monthly | 252d | Trend |
| S5 | Donchian 20/10 breakout | Event (signal) | 20d / 10d | Trend/breakout |
| S7 | Halloween | Annual | Calendar | Seasonal |
| S8 | Turn-of-month | Monthly | Calendar 4-day window | Seasonal |
| S9 | Risk parity 8-ETF | Monthly | 60d sigma | Position sizing |
| S10 | Sector rotation + vol-target | Monthly | 126d rank / 20d sigma | Trend + Position sizing |

All six are old, published, have identifiable losing counterparties, and apply to daily ETF data retrievable via yfinance (with `.TO` suffix for Canadian listings).

---

# References

- Asness, C., Moskowitz, T., & Pedersen, L. (2013). "Value and Momentum Everywhere." *Journal of Finance*.
- Bouman, S., & Jacobsen, B. (2002). "The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle." *American Economic Review*.
- Carhart, M. (1997). "On Persistence in Mutual Fund Performance." *Journal of Finance*.
- Crabel, T. (1990). *Day Trading with Short Term Price Patterns and Opening Range Breakout*.
- Faith, C. (2007). *Way of the Turtle*.
- Faber, D. (2007). "A Quantitative Approach to Tactical Asset Allocation." *Journal of Wealth Management*.
- Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns." *Review of Financial Studies*.
- Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance*.
- Keim, D. (1983). "Size-related Anomalies and Stock Return Seasonality." *Journal of Financial Economics*.
- Lakonishok, J., & Smidt, S. (1988). "Are Seasonal Anomalies Real? A Ninety-Year Perspective." *Review of Financial Studies*.
- Lehmann, B. (1990). "Fads, Martingales and Efficiency." *NBER Working Paper*.
- Maillard, S., Roncalli, T., & Teiletche, J. (2010). "The Properties of Equally Weighted Risk Contribution Portfolios." *Journal of Portfolio Management*.
- Moskowitz, T., Ooi, Y., & Pedersen, L. (2012). "Time Series Momentum." *Journal of Financial Economics*.
- Ogden, J. (1990). "Turn-of-the-Month Evaluations of Liquid Wealth and Stock Returns." *Journal of Financial Economics*.
- Ritter, J. (1988). "The Buying and Selling Behavior of Individual Investors at the Turn of the Year." *Journal of Finance*.
- Wilkinson, J. (2000). Sector rotation literature.
