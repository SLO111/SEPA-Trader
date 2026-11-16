import pandas as pd

from engine import move_detector as md
from engine.scanner import scan_universe
from engine.sepa import rs_ratings, trend_template
from engine.data.providers import SyntheticProvider
from engine.trendlines import auto_trendlines
from engine.vcp import detect_vcp

from .synthetic_patterns import downtrend_stock, flat_benchmark, vcp_stock


def test_vcp_detected_with_correct_pivot():
    df = vcp_stock()
    v = detect_vcp(df)
    assert v["detected"], v
    depths = [c["depth_pct"] for c in v["contractions"]]
    assert len(depths) >= 3 and depths == sorted(depths, reverse=True)
    assert 96 <= v["pivot"] <= 98.5  # the peak of the last contraction
    assert v["stop"] < v["pivot"] and v["volume_dryup"]


def test_no_vcp_in_downtrend():
    assert not detect_vcp(downtrend_stock())["detected"]


def test_trend_template():
    up = trend_template(vcp_stock(), rs_rating=95)
    down = trend_template(downtrend_stock(), rs_rating=10)
    assert up["passed_count"] >= 7
    assert down["passed_count"] <= 3 and not down["all_passed"]


def test_bull_vs_bear_scores():
    bench = flat_benchmark(400)
    up = md.analyze(vcp_stock(), bench, rs_rating=95)
    down = md.analyze(downtrend_stock(), bench, rs_rating=5)
    assert up["bull"]["score"] > 60 > down["bull"]["score"]
    assert down["bear"]["score"] > 60 > up["bear"]["score"]
    assert abs(sum(f["contribution"] for f in up["bull"]["factors"]) - up["bull"]["score"]) < 0.5


def test_move_detector_has_no_lookahead():
    df, bench = vcp_stock(), flat_benchmark(400)
    full = md.score_series(df, bench)
    cut = md.score_series(df.iloc[:330], bench)
    pd.testing.assert_frame_equal(full.iloc[:330], cut)


def test_rs_ratings_order():
    r = rs_ratings({"A": 0.5, "B": 0.1, "C": -0.2})
    assert r == {"A": 99, "B": 50, "C": 1}


def test_trendlines_shape():
    lines = auto_trendlines(SyntheticProvider().history("AAPL"))
    for l in lines:
        times = [p["time"] for p in l["data"]]
        assert times == sorted(times) and len(set(times)) == len(times)


def test_scan_universe():
    rows = scan_universe(SyntheticProvider().history)
    assert len(rows) > 20
    assert all(1 <= r["rs_rating"] <= 99 for r in rows)
    assert all(0 <= r["bull_score"] <= 100 and 0 <= r["bear_score"] <= 100 for r in rows)


def test_scan_api_plan_gating(client, register):
    h, _ = register("scan-free@test.ro")
    assert client.get("/api/sepa/scan", headers=h).status_code == 403
    rep = client.get("/api/sepa/AAPL", headers=h).json()
    assert rep["move_detector"] is None and len(rep["trend_template"]["criteria"]) == 3  # Free: chart-readable criteria only


def test_scan_api_pro(client, register):
    ha, _ = register("admin2@test.ro")
    # move the user to the Pro plan directly in the database
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter_by(email="admin2@test.ro").one()
        u.plan = "pro"
        db.commit()
    r = client.get("/api/sepa/scan?sort=bear", headers=ha)
    assert r.status_code == 200
    res = r.json()["results"]
    assert [x["bear_score"] for x in res] == sorted([x["bear_score"] for x in res], reverse=True)
    rep = client.get("/api/sepa/NVDA", headers=ha).json()
    assert rep["move_detector"]["bull"]["factors"]
