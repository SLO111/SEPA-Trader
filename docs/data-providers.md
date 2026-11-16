# Market data providers: comparison (November 2026)

Prices are for **individual / personal use** unless stated, as listed by the providers and recent third-party
reviews. Always confirm on the provider's own pricing page before paying. Commercial use (showing the data to
paying users of Vnicorn Investments) almost always requires a separate, more expensive license.

| Provider | Price / month | What you get | Pros | Cons |
|---|---|---|---|---|
| **Yahoo Finance (yfinance)**, current | Free | Prices (EOD + intraday), fundamentals, earnings, analysts, holders, news | Free, very broad coverage | Unofficial (no API contract), can block cloud servers or change without notice, **not allowed for commercial use** |
| **Financial Modeling Prep (FMP)** | Free (250 calls/day) · Starter **$29** ($19 billed yearly) · Premium **$69** ($49 yearly) · Ultimate **$139** ($99 yearly) | US stocks (all), EOD + intraday, financial statements, ratios, earnings calendar & estimates, insider/institutional, news, screener. Starter: 300 calls/min, 5 years history; Premium: 750 calls/min, 30 years | Best value "all-in-one" for this app: almost every Vnicorn Investments feature maps to an FMP endpoint | Commercial/display license is separate and pricier; Starter history (5y) is short for long backtests |
| **Massive (formerly Polygon.io)** | Free (5 calls/min) · Starter **$29** · Developer **$79** · Advanced **$199** (yearly: $24 / $64 / $160) | Very high-quality US prices, trades, quotes, aggregates; unlimited calls on paid plans; history 5 / 10 / 20+ years | Best price data quality, true real-time (Advanced), great websockets for live alerts | Only Advanced is real-time (others 15-min delayed); fundamentals thinner than FMP; priced per asset class |
| **EODHD** | Free (20 calls/day) · EOD **$19.99** · EOD+Intraday **$29.99** · Fundamentals **$59.99** · All-in-One **$99.99** (≈$83 yearly) | Global coverage (70+ exchanges), EOD, intraday, fundamentals, screener, insider transactions | Global markets (incl. Europe), long history, good fundamentals | Personal-use only on standard plans; commercial plans from about $399/month |
| **Finnhub** | Free (60 calls/min, personal) · Market data from about **$50** · Fundamentals about **$50–200** per market · All-in-One about **$3,500** | Real-time US quotes (websocket), statements, estimates, transcripts, news, sentiment | Generous free tier, real-time websocket, earnings transcripts | Modular pricing gets expensive fast; per-market licensing |
| **Twelve Data** | Free (800 credits/day) · Grow **$29** · Pro **$99** · Ultra **$329** | Prices for stocks, ETFs, forex, crypto; technical indicators; some fundamentals | Simple pricing, many asset classes | Fundamentals weaker; credit system |
| **Tiingo** | From **$30–50** | EOD + intraday (IEX), news, fundamentals add-on | Clean, reliable EOD data, cheap | No full real-time (SIP); fundamentals limited |
| **Alpha Vantage** | Free (25 requests/day) · **$49.99** (75/min) to **$249.99** (1,200/min) | Prices, indicators, fundamentals, news | Easy to use, popular | Expensive per request; real-time and 15-min-delayed data need premium |

## Recommendation for Vnicorn Investments

1. **Now, personal use:** Yahoo (free), which is what the app uses.
2. **Next step, still personal:** **FMP Premium (~$49/month billed yearly)**. One API covers prices, fundamentals,
   earnings, analysts, insiders and news for every US stock, with 30 years of history for real backtests.
3. **Live alerts in real time:** add **Massive Advanced ($199/month)** for real-time prices and websockets, or use
   FMP's real-time endpoints if their plan covers your needs.
4. **Before charging customers:** ask FMP / Massive for a **commercial display license** quote. Budget for it in
   your subscription prices.

## Sources
- FMP: https://costkite.com/tools/financial-modeling-prep · https://narwhalapi.com/compare/financial-modeling-prep-review
- Massive / Polygon: https://costkite.com/tools/massive-formerly-polygon-io · https://narwhalapi.com/compare/massive-review · https://marketparquet.com/guides/polygon-io-massive-rebrand
- EODHD: https://eodhd.com/pricing · https://www.findmymoat.com/tools/eodhd
- Finnhub: https://finks.ai/api/compare/finnhub · https://apicostcalc.com/finnhub.html
- Twelve Data / Tiingo / Alpha Vantage: https://algodataindex.com/vs/alphavantage-vs-twelvedata/ · https://aifinhub.io/benchmarks/state-of-ai-market-data-2026/ · https://www.findmymoat.com/vs/alpha-vantage-vs-tiingo
