# SEPA Trader

A stock analysis and trading platform: charts, watchlists, strategy overlays, SEPA analysis (Trend Template, VCP, RS Rating), the **Move Detector** algorithm with a market-wide scanner, subscription plans and an admin panel. Alerts, portfolios, market tools and payments are next.

```
backend/    Python API (FastAPI) + engine/ (data, indicators, strategies, SEPA, Move Detector)
frontend/   web app (Next.js + TypeScript + TradingView Lightweight Charts)
```

## Running locally

You need **Python 3.11+** and **Node.js 20+**.

### 1. Backend (in one terminal)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then set ADMIN_EMAIL to your email
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

### 2. Frontend (in another terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and sign up **with the email you set as `ADMIN_EMAIL`**. That account becomes the administrator.

### Market data
- `DATA_PROVIDER=yfinance`: real prices from Yahoo Finance, free and delayed. Suitable for personal use.
- `DATA_PROVIDER=synthetic`: locally generated demo data, no internet needed (NOT real prices).
- Serving paying users requires a provider with a commercial license (e.g. Polygon, FMP).

## Deploying for free (Render.com)

GitHub Pages only hosts static sites, and this app also has a Python server and a database. **Render.com** has a free plan and connects directly to the GitHub repository.

1. Open https://render.com/deploy?repo=https://github.com/SLO111/SEPA-Trader and sign in with GitHub.
2. Render reads `render.yaml` and proposes the `sepa-trader` web service (Docker) and the `sepa-trader-db` database (PostgreSQL).
3. Enter your email for `ADMIN_EMAIL`, then click **Deploy Blueprint**.
4. After the build (5–10 minutes), the app is live at `https://sepa-trader.onrender.com` (or a similar URL shown in Render).
5. Sign up in the app with the `ADMIN_EMAIL` address to get administrator access.

Every `git push` to `main` redeploys automatically.

**Free plan limits:** the service sleeps after 15 minutes without visitors, and the first request afterwards takes about a minute. The free PostgreSQL database expires after 30 days; for real use, upgrade (~$7/month) or point `DATABASE_URL` at an external free database (e.g. Neon).

The `Dockerfile` also works on other platforms: Fly.io, Railway, or any VPS.

### Tests

```bash
cd backend && pytest
```

## Features (stages 1–8)
- Accounts: sign-up, login, admin/user roles, Free / Pro / Premium plans with enforced limits.
- Candlestick charts with volume and 1D / 1W / 1M timeframes.
- Multiple watchlists (create, rename, color, delete; live price and daily change).
- Strategy panel with every available strategy. Stack as many as your plan allows, each with its own parameters:
  SMA 50/100/200, SMA 50/150/200 (SEPA), custom SMA, EMA 10/21, Bollinger Bands, RSI, MACD,
  MA crossover bot (BUY/SELL), RSI reversal bot, Trend Template, VCP + pivot, automatic trend lines, Move Detector.
- **SEPA analysis** for every ticker (strip under the chart): RS Rating 1–99, Trend Template (8 criteria),
  VCP detection with pivot, stop and risk.
- **Move Detector (layer 1)**: Bull Score and Bear Score 0–100 with a per-factor breakdown:
  volatility contraction, volume dry-up/accumulation, trend, relative strength, proximity to pivot, market regime;
  and trend breakdown, distribution days, relative weakness, climax, failed breakout.
- **Scanner** (Move Detector page): the whole market ranked by Bull / Bear / RS, with Trend Template 8/8 and VCP filters.
  Pro and Premium only.
- **Alerts (Move Detector layer 2)**: rules on a single symbol, a watchlist or the entire market, for
  breakouts above the pivot on volume, unusual volume, gaps up/down, 50-day MA breaks, failed breakouts,
  21-day EMA reclaims, RS line new highs, Bull/Bear Score thresholds and custom price levels.
  Checked in the background every 5 minutes (or on demand with **Check now**), deduplicated per bar,
  with in-app notifications plus optional email and Telegram. Pro and Premium only.
- **Portfolios**: multiple portfolios built from a buy/sell ledger (average-cost method, fees, fractional shares).
  Market value, daily change, unrealized and realized P/L, dividends received, and time-weighted performance
  for 1W / 1M / 3M / 6M / YTD / 1Y / all-time or a custom date range, compared with the S&P 500.
- **Automatic portfolio profile**: from the tickers you hold, each portfolio is classified as Aggressive Growth,
  Growth, Momentum, Conservative, Dividend Income, Value, Blue Chip, Defensive, Small & Mid Cap, Speculative,
  Balanced or sector-concentrated, including combinations (e.g. "Dividend Income + Conservative"), with a
  1–5 risk level, style scores, sector allocation and plain-English insights. The portfolio list shows each
  portfolio's profile at a glance.
- **Model portfolios**: ten ready-made mixes (Aggressive Growth, Tech Innovation, Momentum Leaders refreshed from
  the live scanner, Quality Growth, Blue Chip Core, Balanced, Value, Dividend Income, Defensive, Conservative),
  created in one click for any amount.
- **Ticker page** (search any symbol from the header): price chart and period returns, an automated summary with
  positive/negative takeaways, key statistics (valuation, margins, growth, balance sheet), SEPA analysis,
  company profile and peers; plus tabs for annual/quarterly financials, earnings (estimates vs. actuals),
  dividends, analyst ratings and price targets, ownership and insider trades, and news.
- **PDF report** for any company (Premium): summary, price chart with 50/200-day SMAs, key statistics, returns,
  SEPA checklist, financials, earnings, analyst ratings and peers. See `docs/sample-report.pdf` (demo data).
- In demo mode (`DATA_PROVIDER=synthetic`) company data is generated and clearly labeled; news, named holders
  and insider trades are only shown with a live data provider.
- **Markets page**:
  - Overview: S&P 500, Nasdaq 100, Dow, Russell 2000 and VIX; top gainers / losers / most active; market breadth;
    sector rotation with emerging themes; market leaders.
  - **Fear & Greed index**: SEPA Trader's own sentiment gauge (0 = extreme fear, 100 = extreme greed) built from six
    components (market momentum, stock price strength, breadth, volatility, safe-haven demand, junk-bond demand),
    each scored against its own last 12 months, with a 1-year history and previous close / week / month / year.
  - Earnings calendar: upcoming reports (90 days) and recent results with EPS surprise and the price reaction.
  - Pre-market and after-hours movers (live data provider only).
  - Fed monitor: target range, effective rate, next FOMC meeting, Treasury yields and the yield curve, a
    market-implied outlook (estimated from T-bill yields) and decision history, from FRED.
  - Screener (Pro/Premium): presets for undervalued, growth at a reasonable price, high dividend, SEPA leaders,
    near 52-week highs, oversold and momentum, plus filters for sector, market cap, P/E, yield, RS and trend.
- **Trading journal**: log long/short trades with stop, target, setup and notes. Analytics include win rate,
  average win vs. loss, expectancy (in %, $ and R), profit factor, max drawdown, streaks, holding times,
  equity curve, monthly P/L, R-multiple distribution and performance by setup. Free plan: 20 trades.
- **Trade Review** (Premium): every closed trade gets an A–F grade with checks for setup quality (Trend Template,
  Bull Score and market at entry), entry vs. pivot, planned risk, stop discipline and exit quality, plus hindsight
  notes. Entry and exit prices that don't match the market on those dates are flagged instead of graded.
- **Backtesting** (Premium):
  - Move Detector validation: hit rate of major up/down moves by score bucket vs. the base rate, top-10 lift and
    forward returns, using only data available on each day (triple-barrier labels).
  - Machine-learning layer: a gradient-boosting model on the same factors, tested walk-forward (trained only on
    data before each test window) and compared with the rule score by AUC and top-10 hit rate.
  - Strategy backtests for the BUY/SELL bots vs. buy & hold: return, CAGR, max drawdown, win rate and trades.
- Admin panel: stats, change plan/role, deactivate accounts. The account matching `ADMIN_EMAIL` is promoted
  to administrator on sign-up or on its next login.

### Email and Telegram notifications (optional)
Set these environment variables (locally in `backend/.env`, on Render under **Environment**):
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- Telegram: create a bot with [@BotFather](https://t.me/BotFather) and set `TELEGRAM_BOT_TOKEN`.
  Each user enters their chat ID on the Alerts page.

On Render's free plan the service sleeps after 15 minutes without traffic, which also pauses background
alert checks. To keep it awake, ping `https://<your-app>.onrender.com/api/health` every 10 minutes with a free
service such as cron-job.org.

### Adding a new strategy
Create a class in `backend/engine/strategies/builtin.py` (or a new module imported there) decorated with `@register`. It shows up automatically in the chart's strategy list.

## Roadmap
9. Stripe payments

> For educational purposes only. Not financial advice.
