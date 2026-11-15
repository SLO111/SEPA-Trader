from app.db import _normalize


def test_database_url_normalization():
    assert _normalize("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert _normalize("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalize("sqlite:///./x.db") == "sqlite:///./x.db"
