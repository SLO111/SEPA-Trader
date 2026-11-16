import httpx

from engine.data.directory import parse, search
from engine.data.finnhub import Finnhub, RateLimiter

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust, Series 1|G|N|N|100|Y|N
ZXZZT|NASDAQ TEST STOCK|G|Y|N|100|N|N
ABCDW|Abcd Corp - Warrant|S|N|N|100|N|N
File Creation Time: 1116202608:00|||||||"""
OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
BRK.B|Berkshire Hathaway Inc. Class B|N|BRK.B|N|100|N|BRK=B
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
APLE|Apple Hospitality REIT, Inc. Common Shares|N|APLE|N|100|N|APLE
File Creation Time: 1116202608:00|||||||"""


def test_directory_parse_and_search():
    d = parse(NASDAQ, OTHER)
    assert set(d) == {"AAPL", "QQQ", "BRK-B", "SPY", "APLE"}  # test issues and warrants skipped, BRK.B -> BRK-B
    assert d["AAPL"]["name"] == "Apple Inc." and d["SPY"]["etf"] and d["BRK-B"]["exchange"] == "NYSE"
    assert [h["symbol"] for h in search(d, "aap")][:1] == ["AAPL"]
    assert [h["symbol"] for h in search(d, "apple")] == ["AAPL", "APLE"]
    assert search(d, "spy")[0]["sector"] == "ETF"


def _fake(routes):
    def handler(req: httpx.Request):
        assert req.url.params["token"] == "k"
        return httpx.Response(200, json=routes[req.url.path.replace("/api/v1", "")])
    return Finnhub("k", httpx.Client(transport=httpx.MockTransport(handler)), RateLimiter(10_000))


def test_finnhub_fundamentals_and_earnings():
    fh = _fake({
        "/stock/profile2": {"name": "NVIDIA Corp", "finnhubIndustry": "Semiconductors", "marketCapitalization": 4_000_000, "weburl": "https://nvidia.com", "country": "US"},
        "/stock/metric": {"metric": {"peTTM": 45.2, "dividendYieldIndicatedAnnual": 0.03, "epsGrowthTTMYoy": 60.1, "beta": 1.9, "52WeekHigh": 212, "52WeekLow": 86}},
        "/stock/earnings": [{"period": "2026-07-31", "estimate": 1.0, "actual": 1.1, "surprisePercent": 10.0}, {"period": "2026-10-31", "estimate": 1.2, "actual": 1.3, "surprisePercent": 8.3}],
        "/calendar/earnings": {"earningsCalendar": [{"date": "2026-11-19", "epsEstimate": 1.4}]},
        "/stock/recommendation": [{"strongBuy": 20, "buy": 30, "hold": 5, "sell": 1, "strongSell": 0}],
        "/company-news": [{"headline": "NVIDIA beats", "url": "https://x.com/a", "source": "Reuters", "datetime": 1763280000}],
    })
    f = fh.fundamentals("NVDA", sector="Technology")
    assert f["market_cap_b"] == 4000.0 and f["pe"] == 45.2 and f["beta"] == 1.9 and f["sector"] == "Technology"
    e = fh.earnings("NVDA")
    assert e["next_date"] == "2026-11-19" and e["history"][0]["date"] == "2026-10-31"
    co = fh.enrich_company({"symbol": "NVDA", "name": "NVDA", "profile": {}, "stats": {}, "valuation": {}, "analysts": None, "news": [], "earnings": {"history": []}})
    assert co["name"] == "NVIDIA Corp" and co["valuation"]["pe"] == 45.2 and co["stats"]["week52_high"] == 212
    assert co["analysts"]["rating"] == "Buy" and co["analysts"]["total"] == 56
    assert co["news"][0]["title"] == "NVIDIA beats" and co["earnings"]["next_date"] == "2026-11-19"
    assert co["profile"]["website"] == "https://nvidia.com"
