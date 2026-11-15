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

## Features (stages 1–3)
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
- Admin panel: stats, change plan/role, deactivate accounts.

### Adding a new strategy
Create a class in `backend/engine/strategies/builtin.py` (or a new module imported there) decorated with `@register`. It shows up automatically in the chart's strategy list.

## Roadmap
4. Real-time alerts (breakouts, unusual volume, gaps, warnings) + email/Telegram notifications
5. Portfolios with automatic classification
6. Full ticker page + PDF report
7. Market tools (earnings, Fed, pre/after-hours, screener, gainers)
8. Journal, Trade Review, backtesting, ML
9. Stripe payments

> For educational purposes only. Not financial advice.
