import pytest
from fastapi.testclient import TestClient

from app import db
from app.csv_import import CSVFormatError, parse_csv

SAMPLE = """Date,Description,Category,Amount
2024-01-05,Coffee,Food,-4.50
2024-01-06,Salary,Income,3000
2024-02-10,Groceries,Food,-82.10
2024-02-12,Netflix,Entertainment,-15.99
"""


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db(path)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_parse_basic():
    rows = parse_csv(SAMPLE)
    assert len(rows) == 4
    assert rows[0].date == "2024-01-05"
    assert rows[0].amount == -4.5
    assert rows[1].category == "Income"


def test_parse_debit_credit_and_date_formats():
    csv = 'Transaction Date,Payee,Debit,Credit\n05/01/2024,Shop,"1,200.00",\n06/01/2024,Refund,,50\n'
    rows = parse_csv(csv)
    assert rows[0].amount == -1200.0
    assert rows[0].category == "Uncategorized"
    assert rows[1].amount == 50.0


def test_parse_missing_columns():
    with pytest.raises(CSVFormatError):
        parse_csv("Foo,Bar\n1,2\n")


def test_import_and_summary(client):
    r = client.post("/api/import", files={"file": ("x.csv", SAMPLE, "text/csv")})
    assert r.status_code == 200
    assert r.json() == {"parsed": 4, "imported": 4, "skipped_duplicates": 0}

    r = client.post("/api/import", files={"file": ("x.csv", SAMPLE, "text/csv")})
    assert r.json()["imported"] == 0
    assert r.json()["skipped_duplicates"] == 4

    s = client.get("/api/summary").json()
    assert s["expenses"] == 102.59
    assert s["income"] == 3000
    assert s["net"] == 2897.41
    assert s["by_category"][0] == {"category": "Food", "total": 86.6, "count": 2}
    assert [m["month"] for m in s["by_month"]] == ["2024-01", "2024-02"]

    s = client.get("/api/summary", params={"start": "2024-02-01"}).json()
    assert s["count"] == 2

    t = client.get("/api/transactions", params={"category": "Food"}).json()
    assert t["total"] == 2
    assert t["items"][0]["description"] == "Groceries"


def test_import_bad_csv(client):
    r = client.post("/api/import", files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert r.status_code == 400
    assert "date" in r.json()["detail"]


def test_clear(client):
    client.post("/api/import", files={"file": ("x.csv", SAMPLE, "text/csv")})
    assert client.delete("/api/transactions").json()["deleted"] == 4
    assert client.get("/api/summary").json()["count"] == 0
