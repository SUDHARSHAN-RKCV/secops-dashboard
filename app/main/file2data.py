# app/main/file2data.py

import os
import pandas as pd
from datetime import datetime, timedelta, timezone
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_file, send_from_directory,
    session, url_for,
)
from pathlib import Path
from typing import List, Dict, Tuple
main = Blueprint("main", __name__, template_folder="templates")
IST = timezone(timedelta(hours=5, minutes=30))
IST_STAMP = "%Y-%m-%d IST"

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_UI_SOURCE = Path(__file__).resolve().parents[3] / "source" / "ui"
# -------------------------------------------------------------
# 2) Utility: clean multi-index flattening artifacts
# -------------------------------------------------------------
def clean_flat_headers(columns):
    """Flatten pandas MultiIndex or tuple-like headers into simple strings."""
    cleaned = []
    for col in columns:
        # If tuple (from MultiIndex), filter out empty/unnamed parts
        if isinstance(col, tuple):
            parts = [str(c).strip() for c in col if str(c).strip() not in ("", "Unnamed: 0_level_1", 
                                                                           "Unnamed: 1_level_1", 
                                                                           "Unnamed: 7_level_1",
                                                                           "Unnamed: 8_level_1",
                                                                           "Unnamed")]
            col_str = " ".join(parts)
        else:
            col_str = str(col).strip()
        cleaned.append(col_str)
    return cleaned

# -------------------------------------------------------------
# 3) header-flexible Excel reader (primary function)
# -------------------------------------------------------------
def read_excel_with_flexible_headers(xls: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    """Read VAPT sheets with optional multi-index headers."""
    try:
        df = pd.read_excel(xls, sheet_name=sheet, header=[0, 1])

        # Decide if it's a real multi-header
        lvl1 = df.columns.get_level_values(1)
        non_empty = sum([str(x).strip() not in ("", "nan") for x in lvl1])

        if non_empty >= 3:
            df.columns = clean_flat_headers(df.columns)
        else:
            df = pd.read_excel(xls, sheet_name=sheet, header=0)
            df.columns = [str(c).strip() for c in df.columns]

        df = df.dropna(how="all")
        return df

    except Exception:
        df = pd.read_excel(xls, sheet_name=sheet, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all")

# -------------------------------------------------------------
# 4) Utility: Format month-year cells safely
# -------------------------------------------------------------
def safe_format_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        series = df[col]
        if series.dropna().empty:
            continue

        try:
            parsed = pd.to_datetime(series, errors="coerce", format="%b-%Y")
            # Apply only if majority parses successfully
            if parsed.notna().sum() >= len(parsed) / 2:
                df[col] = parsed.dt.strftime("%b-%Y").fillna(series)
        except Exception:
            pass

    return df.fillna("")


# -------------------------------------------------------------
# 5) Generic loader for simple Excel tables
# -------------------------------------------------------------
def load_excel_data(path: str) -> tuple[list, list]:
    if not os.path.exists(path):
        return [], []

    try:
        df = pd.read_excel(path)
        df = safe_format_dates(df)
        df.columns = [str(c).strip() for c in df.columns]
        return list(df.columns), df.to_dict(orient="records")

    except Exception as e:
        current_app.logger.error(f"Failed to load {path}: {e}")
        return [], []


# -------------------------------------------------------------
# 6) VAPT Loader — flexible, robust, multi-sheet aware
# -------------------------------------------------------------
def load_vapt_tracker(path: str, sheet: str | None) -> tuple[list, list, list, str | None]:
    """Load VAPT tracker with multi-sheet handling + flattened headers."""
    if not os.path.exists(path):
        return [], [], [], None

    try:
        xls = pd.ExcelFile(path)
        sheet_names = xls.sheet_names
        selected_sheet = sheet or (sheet_names[-1] if sheet_names else None)

        if not selected_sheet:
            return [], [], sheet_names, None

        df = read_excel_with_flexible_headers(xls, selected_sheet)

        # Flatten headers for consistent rendering
        df.columns = clean_flat_headers(df.columns)

        df = df.dropna(how="all")
        return list(df.columns), df.to_dict(orient="records"), sheet_names, selected_sheet

    except Exception as e:
        current_app.logger.error(f"Failed to load VAPT tracker: {e}")
        return [], [], [], None

def parse_excel(file_path) -> pd.DataFrame:
    """Read an Excel file, ensuring clean string headers."""
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        if df.columns.isnull().any():
            df.columns = df.iloc[0]
            df = df[1:]
        df.columns = [str(col).strip() for col in df.columns]
        return df
    except Exception as exc:
        logger.error("Excel parsing failed for %s: %s", file_path, exc)
        return pd.DataFrame()
    
def get_folder_listing(rel_path: str) -> dict | None:
    """Return a directory-tree dict rooted at BASE_DIR / rel_path."""
    base_dir = str(current_app.config["BASE_DIR"])
    abs_path = os.path.normpath(os.path.join(base_dir, rel_path or ""))
    if not abs_path.startswith(base_dir) or not os.path.isdir(abs_path):
        return None

    items = [
        {
            "name": name,
            "path": os.path.relpath(
                os.path.join(abs_path, name), base_dir
            ).replace("\\", "/"),
            "type": "directory" if os.path.isdir(os.path.join(abs_path, name)) else "file",
        }
        for name in sorted(os.listdir(abs_path))
    ]
    return {
        "name": "" if rel_path == "" else os.path.basename(abs_path),
        "path": rel_path or "",
        "type": "directory",
        "children": items,
    }


def format_dates_dynamic(df: pd.DataFrame) -> pd.DataFrame:
    """
    For every column whose name contains "date", attempt to parse and reformat
    values to dd-MMM-yy.  Unparseable cells keep their original string value;
    NaN becomes an empty string.
    """
    def _col_key(col) -> str:
        if isinstance(col, tuple):
            return "_".join(str(c) for c in col if c)
        return str(col)

    out = df.copy()
    for col in df.columns:
        if "date" not in _col_key(col).lower():
            continue

        parsed = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce")
        formatted = parsed.dt.strftime("%d-%b-%y")
        fallback = df[col].where(df[col].notna(), "").astype(str)

        out[col] = formatted.where(parsed.notna(), fallback).replace("nan", "")

    return out.where(out.notna(), "")

def format_utc(ts: float) -> str:
    """Format a filesystem timestamp as a human-readable IST date string."""
    return datetime.fromtimestamp(ts, tz=IST).strftime(IST_STAMP)


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns to a single readable string level."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " | ".join(str(c) for c in col if c and str(c) != "nan")
            for col in df.columns
        ]
    else:
        df = df.copy()
        df.columns = [str(c) for c in df.columns]
    return df
