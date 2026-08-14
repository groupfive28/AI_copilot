"""
One-off loader: reads PENTA CITIZEN_DATABASE.xlsx (NIN, BVN, Voters Card,
Intl Passport, Drivers License, National ID, CAC Database_TIN - "Image
Creation" is intentionally excluded pending confirmation of its contents)
and loads each sheet into its own Postgres table under the
penta_document_registries schema.

Usage:
    python scripts/load_document_registries.py path/to/workbook.xlsx
    python scripts/load_document_registries.py path/to/workbook.xlsx --if-exists append
    python scripts/load_document_registries.py path/to/workbook.xlsx --yes  # skip confirmation

Connection:
    Reads DATABASE_URL from the environment, or from backend/.env if present -
    same convention as the FastAPI app, so this works against local Postgres
    or Supabase with no code changes.

Naming convention:
    SHEET_TABLE_MAP below reflects the confirmed mapping for this workbook.
    Sheet-name keys must match the workbook's actual sheet names exactly
    (case-sensitive). The script prints the resolved mapping and asks for
    confirmation before touching the database, unless run with --yes.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import BigInteger, Boolean, DateTime, Float, Text

# Confirmed sheet -> table mapping (PENTA CITIZEN_DATABASE.xlsx).
# "Image Creation" is deliberately excluded pending confirmation of its contents.
SHEET_TABLE_MAP: dict[str, str] = {
    "NIN": "nin_registry",
    "BVN": "bvn_registry",
    "Voters Card": "voters_id_registry",
    "Intl Passport": "passport_registry",
    "Drivers License": "drivers_license_registry",
    "National ID": "national_id_registry",
    "CAC Database_TIN": "cac_tin_registry",
}

TARGET_SCHEMA = "penta_document_registries"

TYPE_CHOICES = {
    "text": Text,
    "integer": BigInteger,
    "float": Float,
    "boolean": Boolean,
    "datetime": DateTime,
}


def validate_headers(sheet_name: str, df: pd.DataFrame) -> list[str]:
    """Flags header problems that need a human decision, not a guess."""
    problems = []
    columns = list(df.columns)

    unnamed = [c for c in columns if str(c).startswith("Unnamed:")]
    if unnamed:
        problems.append(f"{len(unnamed)} column(s) have no header text in the sheet")

    dupes = sorted({str(c) for c in columns if columns.count(c) > 1})
    if dupes:
        problems.append(f"duplicate column headers: {dupes}")

    return problems


def infer_column_type(series: pd.Series) -> tuple[type, list[str]]:
    """
    Returns (sqlalchemy_type, warnings). A non-empty warnings list means the
    inferred type is a guess, not a confident read, and should be escalated
    to an interactive prompt rather than loaded silently.
    """
    non_null = series.dropna()

    if non_null.empty:
        return Text, ["column is entirely empty - cannot infer a type"]

    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return Boolean, []
    if pd.api.types.is_integer_dtype(dtype):
        return BigInteger, []
    if pd.api.types.is_float_dtype(dtype):
        return Float, []
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return DateTime, []

    # object dtype: Excel/pandas falls back to this whenever a column mixes
    # types (e.g. some cells numeric, some text) - check for that explicitly.
    python_types = sorted({type(v).__name__ for v in non_null})
    if len(python_types) > 1:
        return Text, [f"mixed value types in this column: {python_types}"]

    return Text, []


def resolve_ambiguous_columns(
    sheet_name: str, df: pd.DataFrame, warnings_by_column: dict[str, list[str]]
) -> dict[str, type]:
    """Interactively asks the user how to type each ambiguous column."""
    overrides: dict[str, type] = {}
    for col, warns in warnings_by_column.items():
        print(f"\n[{sheet_name}] Column '{col}' looks ambiguous:")
        for w in warns:
            print(f"  - {w}")
        print("  Sample values:", df[col].dropna().head(5).tolist())
        choice = (
            input(f"  SQL type for '{col}' (text/integer/float/boolean/datetime) [text]: ")
            .strip()
            .lower()
            or "text"
        )
        overrides[col] = TYPE_CHOICES.get(choice, Text)
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workbook", type=Path, help="Path to the .xlsx file")
    parser.add_argument(
        "--if-exists",
        choices=["fail", "replace", "append"],
        default="fail",
        help="Behavior if a target table already exists (default: fail).",
    )
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set (check backend/.env or your shell environment).")

    if not args.workbook.exists():
        sys.exit(f"Workbook not found: {args.workbook}")

    xl = pd.ExcelFile(args.workbook)
    actual_sheets = xl.sheet_names

    print("Sheets found in workbook:", actual_sheets)
    print("\nProposed sheet -> table mapping:")
    plan: dict[str, str] = {}
    for sheet in actual_sheets:
        table = SHEET_TABLE_MAP.get(sheet)
        print(f"  '{sheet}' -> {table if table else '*** NOT MAPPED - will be skipped ***'}")
        if table:
            plan[sheet] = table

    missing = [s for s in SHEET_TABLE_MAP if s not in actual_sheets]
    if missing:
        print("\nWarning: expected sheets not found in workbook:", missing)

    if not plan:
        sys.exit("No sheets matched SHEET_TABLE_MAP - update it to match this workbook's sheet names, then rerun.")

    if not args.yes:
        confirm = input(f"\nProceed loading into schema '{TARGET_SCHEMA}' with this mapping? [y/N]: ").strip().lower()
        if confirm != "y":
            sys.exit("Aborted - edit SHEET_TABLE_MAP or pass matching sheet names, then rerun.")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TARGET_SCHEMA}"'))

    for sheet_name, table_name in plan.items():
        df = xl.parse(sheet_name)

        header_problems = validate_headers(sheet_name, df)
        if header_problems:
            print(f"\n[{sheet_name}] Cannot proceed automatically:")
            for p in header_problems:
                print(f"  - {p}")
            sys.exit(f"Fix the source sheet or tell me the intended schema for '{sheet_name}', then rerun.")

        dtype_map: dict[str, type] = {}
        warnings_by_column: dict[str, list[str]] = {}
        for col in df.columns:
            sql_type, warns = infer_column_type(df[col])
            dtype_map[col] = sql_type
            if warns:
                warnings_by_column[str(col)] = warns

        if warnings_by_column:
            dtype_map.update(resolve_ambiguous_columns(sheet_name, df, warnings_by_column))

        print(f"\nLoading '{sheet_name}' ({len(df)} rows) -> {TARGET_SCHEMA}.{table_name} ...")
        df.to_sql(
            table_name,
            engine,
            schema=TARGET_SCHEMA,
            if_exists=args.if_exists,
            index=False,
            dtype={col: sql_type() for col, sql_type in dtype_map.items()},
        )
        print("  Done.")

    print("\nAll sheets processed.")


if __name__ == "__main__":
    main()
