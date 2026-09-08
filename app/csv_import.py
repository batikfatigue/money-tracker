"""Parse bank/expense CSV exports into normalized transaction rows.

Accepts flexible column names so exports from most banks work without
reformatting. Supported column aliases (case-insensitive):

- date:        date, transaction date, posted date, trans date
- description: description, memo, payee, name, details, narrative
- category:    category, type
- amount:      amount, value, sum  (negative = expense, positive = income)
  or separate debit/credit (withdrawal/deposit) columns.
"""

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime

DATE_COLS = ("date", "transaction date", "posted date", "trans date", "transaction_date")
DESC_COLS = ("description", "memo", "payee", "name", "details", "narrative")
CATEGORY_COLS = ("category", "type")
AMOUNT_COLS = ("amount", "value", "sum")
DEBIT_COLS = ("debit", "withdrawal", "expense", "money out")
CREDIT_COLS = ("credit", "deposit", "income", "money in")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y")


@dataclass
class Transaction:
    date: str
    description: str
    category: str
    amount: float

    @property
    def fingerprint(self) -> str:
        raw = f"{self.date}|{self.description}|{self.category}|{self.amount:.2f}"
        return hashlib.sha1(raw.encode()).hexdigest()


class CSVFormatError(ValueError):
    pass


def _find(headers: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in headers:
            return headers[c]
    return None


def _parse_date(value: str) -> str:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise CSVFormatError(f"Unrecognized date format: {value!r}")


def _parse_amount(value: str) -> float:
    cleaned = value.strip().replace(",", "").replace("$", "")
    if not cleaned:
        return 0.0
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amt = float(cleaned)
    except ValueError as e:
        raise CSVFormatError(f"Invalid amount: {value!r}") from e
    return -abs(amt) if negative else amt


def parse_csv(content: bytes | str) -> list[Transaction]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CSVFormatError("CSV has no header row")

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    date_col = _find(headers, DATE_COLS)
    desc_col = _find(headers, DESC_COLS)
    cat_col = _find(headers, CATEGORY_COLS)
    amount_col = _find(headers, AMOUNT_COLS)
    debit_col = _find(headers, DEBIT_COLS)
    credit_col = _find(headers, CREDIT_COLS)

    if not date_col:
        raise CSVFormatError("CSV is missing a date column")
    if not desc_col:
        raise CSVFormatError("CSV is missing a description column")
    if not amount_col and not (debit_col or credit_col):
        raise CSVFormatError("CSV is missing an amount (or debit/credit) column")

    rows: list[Transaction] = []
    for i, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            date = _parse_date(row[date_col] or "")
            if amount_col:
                amount = _parse_amount(row[amount_col] or "")
            else:
                debit = _parse_amount(row[debit_col] or "") if debit_col else 0.0
                credit = _parse_amount(row[credit_col] or "") if credit_col else 0.0
                amount = credit - abs(debit)
        except CSVFormatError as e:
            raise CSVFormatError(f"Row {i}: {e}") from e
        category = (row[cat_col] or "").strip() if cat_col else ""
        rows.append(
            Transaction(
                date=date,
                description=(row[desc_col] or "").strip(),
                category=category or "Uncategorized",
                amount=round(amount, 2),
            )
        )
    return rows
