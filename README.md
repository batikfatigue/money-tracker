# Money Tracker

A small self-hosted expense tracker: import bank CSV exports, see an overview of spending by category and month, and browse/filter transactions.

- Backend: FastAPI + SQLite (no external services)
- Frontend: vanilla JS + Chart.js (served by the backend)

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and import `sample_data/transactions.csv` to try it out.

## Login

Set `MONEY_TRACKER_PASSWORD` to require a password; the UI and all `/api/*` routes are then protected by a
signed session cookie (30 days). Optionally set `MONEY_TRACKER_SECRET` to a random string so sessions survive a
password change. When `MONEY_TRACKER_PASSWORD` is unset (local dev) the app is open.

## CSV format

The importer follows the [Lunch Money CSV import format](https://support.lunchmoney.app/guides/import-via-csv). A header row is required; header names are matched case-insensitively.

| Column                  | Required | Notes                                                        |
|-------------------------|----------|--------------------------------------------------------------|
| `date`                  | yes      | `YYYY-MM-DD` or `YYYY/MM/DD` preferred (US/EU and `April 25, 2026` styles also parse) |
| `payee` (or `description`) | yes   | Name of the transaction                                      |
| amount columns          | yes      | One of the three notations below                             |
| `notes`                 | no       | Free text                                                    |
| `categories`            | no       | Defaults to `Uncategorized`                                  |
| `tags`                  | no       | Comma-separated list                                         |

Amount notations:

1. **Single column** — `amount` (or `debit/credit`) with a sign: `-38.50` is an expense, `+100` is income.
2. **Double column** — `debit` + `credit`, or `outflow` + `inflow`. Values are absolute; the column decides the sign.
3. **Amount + type** — `amount` plus an `amount type` (or `debit/credit`) column whose value is one of `outflow`, `inflow`, `debit`, `credit`.

Re-importing the same file is safe: identical rows are skipped as duplicates.

## API

- `POST /api/import` — multipart `file` upload
- `GET /api/summary?start=&end=` — totals, by-category and by-month breakdowns
- `GET /api/transactions?start=&end=&category=&limit=&offset=`
- `DELETE /api/transactions` — remove all data

## Development

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

The SQLite database lives at `data/money.db` (override with `MONEY_TRACKER_DB`).
