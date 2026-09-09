import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app import auth, db
from app.csv_import import CSVFormatError, parse_csv

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    yield


app = FastAPI(title="Money Tracker", lifespan=lifespan)


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    public = path in ("/login", "/logout") or path.startswith("/static/")
    if auth.enabled() and not public and not auth.verify_token(request.cookies.get(auth.COOKIE_NAME)):
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/login")
def login_page(request: Request) -> Response:
    if not auth.enabled() or auth.verify_token(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.post("/login")
def login(request: Request, password: Annotated[str, Form()]) -> Response:
    if not auth.check_password(password):
        return RedirectResponse("/login?error=1", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        auth.COOKIE_NAME,
        auth.issue_token(),
        max_age=auth.SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return resp


@app.post("/logout")
def logout() -> Response:
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/api/auth")
def auth_status() -> dict:
    return {"enabled": auth.enabled()}


@app.post("/api/import")
async def import_csv(file: Annotated[UploadFile, File()]) -> dict:
    content = await file.read()
    try:
        rows = parse_csv(content)
    except CSVFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    imported = 0
    with db.get_conn() as conn:
        for t in rows:
            cur = conn.execute(
                "INSERT OR IGNORE INTO transactions "
                "(date, payee, category, amount, notes, tags, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t.date, t.payee, t.category, t.amount, t.notes, ",".join(t.tags), t.fingerprint),
            )
            imported += cur.rowcount
    return {"parsed": len(rows), "imported": imported, "skipped_duplicates": len(rows) - imported}


def _range_clause(start: str | None, end: str | None) -> tuple[str, list]:
    clauses, params = [], []
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.get("/api/transactions")
def list_transactions(
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    where, params = _range_clause(start, end)
    if category:
        where += (" AND " if where else " WHERE ") + "category = ?"
        params.append(category)
    with db.get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM transactions{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT id, date, payee, category, amount, notes, tags FROM transactions{where} "
            "ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item["tags"] = [t for t in item["tags"].split(",") if t]
        items.append(item)
    return {"total": total, "items": items}


@app.get("/api/summary")
def summary(start: str | None = None, end: str | None = None) -> dict:
    where, params = _range_clause(start, end)
    with db.get_conn() as conn:
        totals = conn.execute(
            f"""SELECT
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount END), 0) AS expenses,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount END), 0) AS income,
                COUNT(*) AS count
            FROM transactions{where}""",
            params,
        ).fetchone()
        by_category = conn.execute(
            f"""SELECT category, ROUND(SUM(-amount), 2) AS total, COUNT(*) AS count
            FROM transactions{where}{" AND" if where else " WHERE"} amount < 0
            GROUP BY category ORDER BY total DESC""",
            params,
        ).fetchall()
        by_month = conn.execute(
            f"""SELECT substr(date, 1, 7) AS month,
                ROUND(COALESCE(SUM(CASE WHEN amount < 0 THEN -amount END), 0), 2) AS expenses,
                ROUND(COALESCE(SUM(CASE WHEN amount > 0 THEN amount END), 0), 2) AS income
            FROM transactions{where}
            GROUP BY month ORDER BY month""",
            params,
        ).fetchall()
    expenses = round(totals["expenses"], 2)
    income = round(totals["income"], 2)
    return {
        "expenses": expenses,
        "income": income,
        "net": round(income - expenses, 2),
        "count": totals["count"],
        "by_category": [dict(r) for r in by_category],
        "by_month": [dict(r) for r in by_month],
    }


@app.delete("/api/transactions")
def clear_transactions() -> dict:
    with db.get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions")
    return {"deleted": cur.rowcount}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
