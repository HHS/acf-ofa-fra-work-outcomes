"""
Parse a fixed-width QW file (with MTH header, QWM detail, MTT trailer)
into pandas DataFrames in memory.

- Uses width definitions (dict of field->width)
- Supports multiple record types by record_identifier (MTH/QWM/MTT)
- Optionally validates trailer counts (qw_records, total_records)
- Keeps all fields as strings by default (safe for leading zeros)

Usage:
  python ndnh_qwm_output_parse.py --path ORG.EXPSXXM1.FPLS.R250615

Or import:
  from ndnh_qwm_output_parse import parse_qw_file
  res = parse_qw_file("ORG.EXPSXXM1.FPLS.R250615")
  header_df, detail_df, trailer_df = res.header, res.detail, res.trailer
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd


# ----------------------------
# Fixed-width definitions
# ----------------------------
DETAIL_WIDTHS: Dict[str, int] = {
    "submitter_identifier": 3,
    "record_identifier": 3,  # "QWM"
    "employee_pseudo_ssn": 9,
    "verification_request": 1,
    "filler1": 55,
    "qw_processed_date": 8, # YYYYMMDD
    "filler2": 62,
    "non_verifiable_indicator": 1,
    "pseudo_fein": 9,
    "filler3": 203,
    "employer_state": 2,      # Postal most of the time
    "filler4": 51,
    "qw_employee_wage": 11,   # zero padded digits
    "qw_reporting_period": 5, # QYYYY - calendar quarters
    "filler6": 200,
    "submitted_state_code": 2,
    "filler7": 36,
    "qw_match_code": 1,
    "qw_same_state_data": 1,
    "qw_from_reporting": 5,
    "qw_through_reporting": 5,
    "qw_from_date": 8,
    "qw_through_date": 8,
    "filler8": 28,
    "transmitter_agency": 1,
    "filler9": 8,
    "transmitter_state_code": 2,  # FIPS
    "filler10": 271,
    "pseudo_fein_indicator": 1,
}
DETAIL_ORDER: List[str] = list(DETAIL_WIDTHS.keys())
DETAIL_RECORD_WIDTH = sum(DETAIL_WIDTHS.values())

HEADER_WIDTHS: Dict[str, int] = {
    "submitter_identifier": 3,
    "record_identifier": 3,      # "MTH"
    "date_processed": 8,
    "submitting_state_code": 2,
    "filler1": 8,
    "batch": 8,
    "filler2": 968,
}
HEADER_ORDER: List[str] = list(HEADER_WIDTHS.keys())
HEADER_RECORD_WIDTH = sum(HEADER_WIDTHS.values())

TRAILER_WIDTHS: Dict[str, int] = {
    "submitter_identifier": 3,
    "record_identifier": 3,  # "MTT"
    "w4_records": 11,
    "ui_records": 11,
    "qw_records": 11,
    "erm_records": 11,
    "total_records": 11,
    "filler1": 939,
}
TRAILER_ORDER: List[str] = list(TRAILER_WIDTHS.keys())
TRAILER_RECORD_WIDTH = sum(TRAILER_WIDTHS.values())


def _slice_fixed_width(line: str, widths: Dict[str, int], order: List[str]) -> Dict[str, str]:
    """Slice a fixed-width line into a dict of field -> raw string (no stripping)."""
    out: Dict[str, str] = {}
    pos = 0
    for name in order:
        w = widths[name]
        out[name] = line[pos : pos + w]
        pos += w
    return out


def _record_identifier(line: str) -> str:
    # record_identifier is always positions [3:6] in all formats here (submitter 3 + record id 3)
    if len(line) < 6:
        return ""
    return line[3:6]


@dataclass
class ParseResult:
    header: pd.DataFrame
    detail: pd.DataFrame
    trailer: pd.DataFrame


def parse_qw_file(
    path: str | Path,
    *,
    strip_fields: bool = True,
    keep_fillers: bool = False,
    validate_trailer: bool = True,
    encoding: str = "utf-8",
) -> ParseResult:
    """
    Parse a fixed width file into DataFrames in memory.

    Parameters
    ----------
    strip_fields : if True, rstrip() all fields (preserves left zeros)
    keep_fillers : if False, drop filler* columns
    validate_trailer : if True, validate trailer counts against parsed content
    """
    p = Path(path)

    header_rows: List[Dict[str, str]] = []
    detail_rows: List[Dict[str, str]] = []
    trailer_rows: List[Dict[str, str]] = []

    with p.open("r", encoding=encoding, newline="") as f:
        for raw in f:
            line = raw.rstrip("\n")
            rid = _record_identifier(line)

            if rid == "MTH":
                if len(line) != HEADER_RECORD_WIDTH:
                    raise ValueError(f"Header width mismatch: got {len(line)} expected {HEADER_RECORD_WIDTH}")
                row = _slice_fixed_width(line, HEADER_WIDTHS, HEADER_ORDER)
                header_rows.append(row)

            elif rid == "QWM":
                if len(line) != DETAIL_RECORD_WIDTH:
                    raise ValueError(f"Detail width mismatch: got {len(line)} expected {DETAIL_RECORD_WIDTH}")
                row = _slice_fixed_width(line, DETAIL_WIDTHS, DETAIL_ORDER)
                detail_rows.append(row)

            elif rid == "MTT":
                if len(line) != TRAILER_RECORD_WIDTH:
                    raise ValueError(f"Trailer width mismatch: got {len(line)} expected {TRAILER_RECORD_WIDTH}")
                row = _slice_fixed_width(line, TRAILER_WIDTHS, TRAILER_ORDER)
                trailer_rows.append(row)

            else:
                # Unknown record type; you can choose to skip or raise
                raise ValueError(f"Unknown record_identifier '{rid}' in line: {line[:40]}...")

    header_df = pd.DataFrame(header_rows)
    detail_df = pd.DataFrame(detail_rows)
    trailer_df = pd.DataFrame(trailer_rows)

    # Optionally strip right-padding spaces from fields
    if strip_fields:
        for df in (header_df, detail_df, trailer_df):
            for c in df.columns:
                df[c] = df[c].astype(str).str.rstrip()

    # Optionally drop filler columns
    if not keep_fillers:
        header_df = header_df[[c for c in header_df.columns if not c.startswith("filler")]]
        detail_df = detail_df[[c for c in detail_df.columns if not c.startswith("filler")]]
        trailer_df = trailer_df[[c for c in trailer_df.columns if not c.startswith("filler")]]

    # Optional trailer validation
    if validate_trailer and not trailer_df.empty:
        # If multiple trailers exist, validate each against the full parsed file
        for _, t in trailer_df.iterrows():
            qw_expected = int(str(t["qw_records"]).strip() or "0")
            total_expected = int(str(t["total_records"]).strip() or "0")
            qw_actual = len(detail_df)
            total_actual = len(header_df) + len(detail_df) + len(trailer_df)

            if qw_expected != qw_actual:
                raise ValueError(f"Trailer qw_records mismatch: expected {qw_expected} actual {qw_actual}")
            if total_expected != total_actual:
                raise ValueError(f"Trailer total_records mismatch: expected {total_expected} actual {total_actual}")

    return ParseResult(header=header_df, detail=detail_df, trailer=trailer_df)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Path to fixed-width file")
    ap.add_argument("--keep-fillers", action="store_true", help="Keep filler columns")
    ap.add_argument("--no-strip", action="store_true", help="Do not strip right-padding spaces")
    ap.add_argument("--no-validate-trailer", action="store_true", help="Do not validate trailer counts")
    args = ap.parse_args()

    result = parse_qw_file(
        args.path,
        strip_fields=not args.no_strip,
        keep_fillers=args.keep_fillers,
        validate_trailer=not args.no_validate_trailer,
    )

    print("Header rows:", len(result.header))
    print(result.header.head())

    print("\nDetail rows:", len(result.detail))
    print(result.detail.head())

    print("\nTrailer rows:", len(result.trailer))
    print(result.trailer.head())


if __name__ == "__main__":
    main()
