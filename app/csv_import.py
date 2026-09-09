"""Parse CSV exports in the Lunch Money import format.

Spec: https://support.lunchmoney.app/guides/import-via-csv

Columns (header names matched case-insensitively):

- ``date``                     required; YYYY-MM-DD / YYYY/MM/DD preferred
- ``payee`` or ``description`` required
- amount, one of three notations:
    1. single column ``amount`` (or ``debit/credit``) with +/- sign
    2. double column ``debit`` + ``credit``, or ``outflow`` + ``inflow``
       (values are absolute; the column decides the sign)
    3. ``amount`` + ``amount type`` (or ``debit/credit`` type column)
       whose values are one of outflow/inflow/debit/credit
- ``notes``                    optional
- ``categories``               optional (``category`` also accepted)
- ``tags``                     optional, comma-separated
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime

DATE_COLS = ("date",)
PAYEE_COLS = ("payee", "description")
NOTES_COLS = ("notes",)
CATEGORY_COLS = ("categories", "category")
TAGS_COLS = ("tags",)
AMOUNT_COLS = ("amount",)
AMOUNT_OR_TYPE_COLS = ("debit/credit",)
AMOUNT_TYPE_COLS = ("amount type", "amount_type", "type")
DEBIT_COLS = ("debit", "outflow")
CREDIT_COLS = ("credit", "inflow")

OUTFLOW_TYPES = {"outflow", "debit"}
INFLOW_TYPES = {"inflow", "credit"}

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


@dataclass
class Transaction:
    date: str
    payee: str
    amount: float
    category: str = "Uncategorized"
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        raw = f"{self.date}|{self.payee}|{self.category}|{self.amount:.2f}|{self.notes}|{','.join(self.tags)}"
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


def _parse_number(value: str) -> float:
    cleaned = value.strip().replace(",", "").replace("$", "").replace(" ", "")
    if not cleaned:
        return 0.0
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amt = float(cleaned)
    except ValueError as e:
        raise CSVFormatError(f"Invalid amount: {value!r}") from e
    return -abs(amt) if negative else amt


def _parse_amount_type(value: str) -> int:
    kind = value.strip().lower()
    if kind in OUTFLOW_TYPES:
        return -1
    if kind in INFLOW_TYPES:
        return 1
    raise CSVFormatError(f"Invalid amount type {value!r}; expected one of outflow, inflow, debit, credit")


def _parse_tags(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def parse_csv(content: bytes | str) -> list[Transaction]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CSVFormatError("CSV has no header row")

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    date_col = _find(headers, DATE_COLS)
    payee_col = _find(headers, PAYEE_COLS)
    notes_col = _find(headers, NOTES_COLS)
    cat_col = _find(headers, CATEGORY_COLS)
    tags_col = _find(headers, TAGS_COLS)
    amount_col = _find(headers, AMOUNT_COLS)
    debit_credit_col = _find(headers, AMOUNT_OR_TYPE_COLS)
    debit_col = _find(headers, DEBIT_COLS)
    credit_col = _find(headers, CREDIT_COLS)

    if not date_col:
        raise CSVFormatError("CSV is missing the required 'date' column")
    if not payee_col:
        raise CSVFormatError("CSV is missing the required 'payee' (or 'description') column")

    # Resolve which amount notation the file uses.
    type_col: str | None = None
    if amount_col:
        type_col = debit_credit_col or _find(headers, AMOUNT_TYPE_COLS)
    elif debit_credit_col:
        amount_col = debit_credit_col  # signed single column named "debit/credit"
    elif not (debit_col or credit_col):
        raise CSVFormatError(
            "CSV is missing an amount column: expected 'amount', 'debit'/'credit', or 'outflow'/'inflow'"
        )

    rows: list[Transaction] = []
    for i, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            date = _parse_date(row[date_col] or "")
            if amount_col:
                amount = _parse_number(row[amount_col] or "")
                if type_col:
                    amount = abs(amount) * _parse_amount_type(row[type_col] or "")
            else:
                debit = abs(_parse_number(row[debit_col] or "")) if debit_col else 0.0
                credit = abs(_parse_number(row[credit_col] or "")) if credit_col else 0.0
                amount = credit - debit
        except CSVFormatError as e:
            raise CSVFormatError(f"Row {i}: {e}") from e

        category = (row[cat_col] or "").strip() if cat_col else ""
        rows.append(
            Transaction(
                date=date,
                payee=(row[payee_col] or "").strip(),
                amount=round(amount, 2),
                category=category or "Uncategorized",
                notes=(row[notes_col] or "").strip() if notes_col else "",
                tags=_parse_tags(row[tags_col] or "") if tags_col else [],
            )
        )
    return rows
