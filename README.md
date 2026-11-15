# SEPA Trader

Platformă de analiză și trading pe acțiuni: charturi, liste de tickere, strategii suprapuse, conturi cu abonament și panou de administrator. Urmează portofoliile, Move Detector, alertele, uneltele de piață și plățile.

```
backend/    API Python (FastAPI) + engine/ (date, indicatori, strategii)
frontend/   aplicația web (Next.js + TypeScript + TradingView Lightweight Charts)
```

## Cum pornești aplicația pe calculatorul tău

Ai nevoie de **Python 3.11+** și **Node.js 20+**.

### 1. Backend (într-un terminal)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # apoi pune emailul tău la ADMIN_EMAIL
uvicorn app.main:app --reload --port 8000
```

Documentația API interactivă: http://localhost:8000/docs

### 2. Frontend (în alt terminal)

```bash
cd frontend
npm install
npm run dev
```

Deschide http://localhost:3000 și creează-ți cont **cu emailul pus la `ADMIN_EMAIL`**: contul acela devine administrator.

### Date de piață
- `DATA_PROVIDER=yfinance`: prețuri reale de la Yahoo Finance, gratuite, cu întârziere. Potrivit pentru uz personal.
- `DATA_PROVIDER=synthetic`: date demo generate local, fără internet (NU sunt prețuri reale).
- Pentru utilizatori plătitori va fi nevoie de un furnizor cu licență comercială (ex. Polygon, FMP).

### Teste

```bash
cd backend && pytest
```

## Ce e gata (etapele 1–2)
- Conturi: înregistrare, login, roluri admin/utilizator, planuri Free / Pro / Premium cu limite.
- Charturi cu lumânări, volum și timeframe-uri 1Z / 1S / 1L.
- Liste multiple de tickere (creezi, redenumești, colorezi, ștergi; prețuri și variații).
- Panou cu toate strategiile, activabile câte vrei deodată, fiecare cu parametri proprii:
  SMA 50/100/200, SMA 50/150/200 (SEPA), SMA la alegere, EMA 10/21, Bollinger, RSI, MACD,
  Bot crossover (BUY/SELL), Bot revenire RSI.
- Panou de administrator: statistici, schimbare plan/rol, dezactivare conturi.

### Cum adaugi o strategie nouă
Creezi o clasă în `backend/engine/strategies/builtin.py` (sau într-un fișier nou importat acolo), decorată cu `@register`. Apare automat în lista de pe pagina de chart.

## Urmează
3. Trend Template, VCP, trend lines + **Move Detector** (Setup Score) + scanner
4. Alerte în timp real (breakout, volum neobișnuit, gap-uri, avertismente)
5. Portofolii cu clasificare automată
6. Pagina completă de ticker + raport PDF
7. Unelte de piață (earnings, Fed, pre/after-hours, screener, gainers)
8. Jurnal, Trade Review, backtesting, ML
9. Plăți Stripe
10. Deploy

> Informațiile din aplicație au scop educațional și nu reprezintă sfat financiar.
