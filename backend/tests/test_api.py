from engine.strategies import REGISTRY


def test_register_login_me(client, register):
    h, user = register("ana@test.ro")
    assert user["plan"] == "free" and user["role"] == "user"
    r = client.post("/api/auth/login", json={"email": "ana@test.ro", "password": "parola123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email"] == "ana@test.ro"
    assert client.post("/api/auth/login", json={"email": "ana@test.ro", "password": "gresit00"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_free_plan_limits(client, register):
    h, _ = register("free@test.ro")
    wls = client.get("/api/watchlists", headers=h).json()
    assert len(wls) == 1 and wls[0]["symbols"][0] == "AAPL"
    # free: a single watchlist
    assert client.post("/api/watchlists", headers=h, json={"name": "A doua"}).status_code == 403
    # free: max 10 symbols (already has 5)
    wl = wls[0]["id"]
    for s in ["GOOGL", "TSLA", "AMD", "NFLX", "CRM"]:
        assert client.post(f"/api/watchlists/{wl}/items", headers=h, json={"symbol": s}).status_code == 200
    assert client.post(f"/api/watchlists/{wl}/items", headers=h, json={"symbol": "KO"}).status_code == 403
    # free: max 3 strategies
    body = {"symbol": "AAPL", "strategies": [{"id": i} for i in list(REGISTRY)[:4]]}
    assert client.post("/api/strategies/run", headers=h, json=body).status_code == 403


def test_watchlist_isolation(client, register):
    h1, _ = register("u1@test.ro")
    h2, _ = register("u2@test.ro")
    wl = client.get("/api/watchlists", headers=h1).json()[0]["id"]
    assert client.delete(f"/api/watchlists/{wl}", headers=h2).status_code == 404


def test_candles_and_all_strategies(client, register):
    h, _ = register("chart@test.ro")
    r = client.get("/api/market/candles/NVDA", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert len(data["candles"]) > 500 and data["name"] == "NVIDIA Corp."
    for sid, cls in REGISTRY.items():
        res = client.post("/api/strategies/run", headers=h, json={"symbol": "NVDA", "strategies": [{"id": sid}]})
        if cls.requires:  # Free account => locked
            assert res.status_code == 403, sid
            continue
        assert res.status_code == 200, sid
        out = res.json()["results"][0]
        assert set(out) == {"lines", "histograms", "markers", "levels"}, sid
        if sid not in ("vcp", "trendlines", "trend_template"):  # may legitimately be empty
            assert out["lines"] or out["markers"], sid


def test_same_indicator_twice_intraday_and_info(client, register):
    h, _ = register("chart2@test.ro")
    body = {"symbol": "AAPL", "strategies": [{"id": "ma", "params": {"period": 20}}, {"id": "ma", "params": {"period": 50, "type": 1}}]}
    res = client.post("/api/strategies/run", headers=h, json=body).json()["results"]
    assert [r["lines"][0]["name"] for r in res] == ["SMA 20", "EMA 50"]

    intra = client.get("/api/market/candles/AAPL?interval=15m", headers=h).json()
    assert {c["session"] for c in intra["candles"]} == {"pre", "regular", "post"}
    assert all(isinstance(c["time"], int) for c in intra["candles"])  # intraday uses timestamps
    r = client.post("/api/strategies/run", headers=h, json={"symbol": "AAPL", "interval": "15m", "strategies": [{"id": "rsi"}]})
    assert r.status_code == 200 and isinstance(r.json()["results"][0]["lines"][0]["data"][0]["time"], int)

    info = client.get("/api/market/info/AAPL", headers=h).json()
    assert info["name"] == "Apple Inc." and info["week52"]["high"] >= info["week52"]["low"]
    assert info["sepa"]["rs_rating"] is not None and info["overnight"] is None


def test_admin(client, register):
    ha, admin = register("admin@test.ro")
    hu, user = register("client@test.ro")
    assert admin["role"] == "admin"
    assert client.get("/api/admin/users", headers=hu).status_code == 403
    r = client.patch(f"/api/admin/users/{user['id']}", headers=ha, json={"plan": "pro"})
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert client.post("/api/watchlists", headers=hu, json={"name": "Lista 2"}).status_code == 200
    assert client.get("/api/admin/stats", headers=ha).json()["total_users"] >= 2
