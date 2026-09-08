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

## CSV format

A header row is required. Column names are matched case-insensitively:

| Field       | Accepted headers                                              |
|-------------|---------------------------------------------------------------|
| date        | `date`, `transaction date`, `posted date`, `trans date`       |
| description | `description`, `memo`, `payee`, `name`, `details`, `narrative`|
| category    | `category`, `type` (optional, defaults to `Uncategorized`)     |
| amount      | `amount`, `value`, `sum` — negative = expense, positive = income |
|             | or `debit`/`withdrawal` + `credit`/`deposit` columns           |

Dates in `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-MM-YYYY`, `YYYY/MM/DD`, `DD Mon YYYY`, `Mon DD, YYYY` are recognized.
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
