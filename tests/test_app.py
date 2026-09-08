import pytest
from fastapi.testclient import TestClient

from app import db
from app.csv_import import CSVFormatError, parse_csv

SAMPLE = """date,payee,amount,notes,categories,tags
2024-01-05,Coffee,-4.50,,Food,coffee
2024-01-06,Salary,3000,January,Income,"work, monthly"
2024-02-10,Groceries,-82.10,,Food,
2024-02-12,Netflix,-15.99,subscription,Entertainment,
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


def test_parse_single_amount_column():
    rows = parse_csv(SAMPLE)
    assert len(rows) == 4
    assert rows[0].date == "2024-01-05"
    assert rows[0].amount == -4.5
    assert rows[0].tags == ["coffee"]
    assert rows[1].category == "Income"
    assert rows[1].notes == "January"
    assert rows[1].tags == ["work", "monthly"]
    assert rows[2].notes == "" and rows[2].tags == []


def test_parse_signed_debit_credit_column_and_description_alias():
    csv = 'Date,Description,Debit/Credit\n"April 25, 2026",Walmart,+100\n"April 21, 2026",Starbucks,-38.50\n'
    rows = parse_csv(csv)
    assert [r.amount for r in rows] == [100.0, -38.5]
    assert rows[0].date == "2026-04-25"
    assert rows[0].payee == "Walmart"
    assert rows[0].category == "Uncategorized"


def test_parse_double_column_is_absolute():
    csv = "Date,Payee,Debit,Credit\n2026/04/25,Walmart,,100\n2026/04/21,Starbucks,38.5,\n"
    csv += "2026/04/20,Costco,-98.99,\n"
    rows = parse_csv(csv)
    assert [r.amount for r in rows] == [100.0, -38.5, -98.99]

    rows = parse_csv("date,payee,outflow,inflow\n2026-04-25,Walmart,,100\n2026-04-21,Starbucks,38.5,\n")
    assert [r.amount for r in rows] == [100.0, -38.5]


def test_parse_amount_plus_type_column():
    csv = "Date,Payee,Amount,Amount Type\n2026-04-25,Walmart,100,Credit\n2026-04-21,Starbucks,38.5,Debit\n"
    csv += "2026-04-20,Costco,-98.99,outflow\n2026-04-19,Refund,20,inflow\n"
    rows = parse_csv(csv)
    assert [r.amount for r in rows] == [100.0, -38.5, -98.99, 20.0]

    rows = parse_csv("date,payee,amount,debit/credit\n2026-04-25,Walmart,100,credit\n")
    assert rows[0].amount == 100.0

    with pytest.raises(CSVFormatError, match="amount type"):
        parse_csv("date,payee,amount,amount type\n2026-04-25,Walmart,100,maybe\n")


def test_parse_missing_columns():
    with pytest.raises(CSVFormatError, match="'date'"):
        parse_csv("payee,amount\nx,1\n")
    with pytest.raises(CSVFormatError, match="'payee'"):
        parse_csv("date,amount\n2024-01-01,1\n")
    with pytest.raises(CSVFormatError, match="amount column"):
        parse_csv("date,payee\n2024-01-01,x\n")


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
    assert t["items"][0]["payee"] == "Groceries"
    assert t["items"][1]["tags"] == ["coffee"]

    t = client.get("/api/transactions", params={"category": "Income"}).json()
    assert t["items"][0]["notes"] == "January"
    assert t["items"][0]["tags"] == ["work", "monthly"]


def test_import_bad_csv(client):
    r = client.post("/api/import", files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert r.status_code == 400
    assert "date" in r.json()["detail"]


def test_clear(client):
    client.post("/api/import", files={"file": ("x.csv", SAMPLE, "text/csv")})
    assert client.delete("/api/transactions").json()["deleted"] == 4
    assert client.get("/api/summary").json()["count"] == 0
