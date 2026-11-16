import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["DATA_PROVIDER"] = "synthetic"
os.environ["ADMIN_EMAIL"] = "admin@test.ro"
os.environ["ALERT_CHECK_SECONDS"] = "0"
os.environ["IDEAS_INTERVAL_SECONDS"] = "0"
os.environ["TRIAL_DAYS"] = "0"  # tests start on Free unless they create a trial

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _register(client, email, password="parola123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Test"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


@pytest.fixture
def register(client):
    return lambda email: _register(client, email)
