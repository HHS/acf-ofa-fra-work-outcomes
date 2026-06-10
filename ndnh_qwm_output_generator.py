"""
Simplified NDNH QWM Fixed-Width File Generator

Core Logic:
1. Generate ALL baseline records (persona × quarter)
2. Assign qw_processed_date to each record based on patterns
3. Partition records into extract files via 2-year window
4. Add variations (late arrivals, corrections, duplicates)

This naturally produces realistic temporal distributions.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import argparse
import random
from typing import List, Dict, Tuple


# Extract configuration
EXTRACTS = {
    "202506": "20250615",  # extract_key: file_date (YYYYMMDD)
    "202509": "20250915",
    "202601": "20260115",
    "202603": "20260315",
}

# State mappings
POSTAL_STATES = ["XA", "XB", "XC", "XD", "XE"]
POSTAL_TO_FIPS = {"XA": "03", "XB": "07", "XC": "14", "XD": "43", "XE": "52"}

# Record width constants (from original spec)
DETAIL_WIDTH = 1000  # Total width of QWM record
HEADER_WIDTH = 1000  # Total width of MTH record  
TRAILER_WIDTH = 1000  # Total width of MTT record


# ============================================================================
# Date & Quarter Utilities
# ============================================================================

def str_to_date(s: str) -> date:
    """YYYYMMDD -> date"""
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def date_to_str(d: date) -> str:
    """date -> YYYYMMDD"""
    return d.strftime("%Y%m%d")


def qyyyy_to_dates(qyyyy: int) -> Tuple[date, date]:
    """Convert QYYYY to (quarter_start, quarter_end) dates"""
    qtr = qyyyy // 10000
    year = qyyyy % 10000
    month = (qtr - 1) * 3 + 1
    start = date(year, month, 1)
    
    if qtr == 4:
        end = date(year, 12, 31)
    else:
        next_month = month + 3
        end = date(year, next_month, 1) - timedelta(days=1)
    
    return start, end


def iter_quarters(start_qyyyy: int, end_qyyyy: int) -> List[int]:
    """Generate list of quarters between start and end (inclusive)"""
    def qyyyy_to_index(q):
        qtr, year = q // 10000, q % 10000
        return year * 4 + (qtr - 1)
    
    def index_to_qyyyy(idx):
        qtr = (idx % 4) + 1
        year = idx // 4
        return qtr * 10000 + year
    
    start_idx = qyyyy_to_index(start_qyyyy)
    end_idx = qyyyy_to_index(end_qyyyy)
    
    return [index_to_qyyyy(i) for i in range(start_idx, end_idx + 1)]


# ============================================================================
# Persona (Synthetic Person)
# ============================================================================

@dataclass(frozen=True)
class Persona:
    person_id: int
    ssn: str
    fein: str
    employer_state: str  # POSTAL
    transmitter_fips: str  # FIPS
    pattern: str  # 'continuous', 'gaps', 'late_start'


def create_personas(n: int, rng: random.Random) -> List[Persona]:
    """Create synthetic personas with employment patterns"""
    personas = []
    
    for i in range(1, n + 1):
        ssn = str(100_000_000 + i).zfill(9)
        fein = str(700_000_000 + (i % 200)).zfill(9)
        
        employer_state = POSTAL_STATES[i % len(POSTAL_STATES)]
        transmitter_fips = POSTAL_TO_FIPS[employer_state]
        
        # Simple pattern distribution
        if i % 10 == 0:
            pattern = 'gaps'  # 10% have gaps
        elif i % 15 == 0:
            pattern = 'late_start'  # ~7% start later
        else:
            pattern = 'continuous'  # ~83% continuous
        
        personas.append(Persona(i, ssn, fein, employer_state, transmitter_fips, pattern))
    
    return personas


def persona_active_in_quarter(p: Persona, qyyyy: int) -> bool:
    """Is this persona employed in this quarter?"""
    if p.pattern == 'continuous':
        return True
    elif p.pattern == 'late_start':
        return qyyyy >= 42023  # Start Q4 2023
    elif p.pattern == 'gaps':
        # Skip one quarter per year (deterministic)
        year = qyyyy % 10000
        qtr = qyyyy // 10000
        skip_qtr = ((p.person_id + year) % 4) + 1
        return qtr != skip_qtr
    return True


def calculate_wage(p: Persona, qyyyy: int) -> int:
    """Calculate wage for this persona/quarter"""
    qtr = qyyyy // 10000
    year = qyyyy % 10000
    
    # Base wage with variation
    base = 15000 + (p.person_id % 20) * 500
    
    # Annual growth
    years_since_2023 = year - 2023
    growth = years_since_2023 * 800
    
    # Seasonal variation
    seasonal = (qtr - 2.5) * 400
    
    wage = int(base + growth + seasonal)
    
    # Some personas occasionally have zero wages
    if p.person_id % 50 == 0 and qyyyy % 2 == 0:
        return 0
    
    return max(0, wage)


# ============================================================================
# Wage Record
# ============================================================================

@dataclass
class WageRecord:
    ssn: str
    fein: str
    employer_state: str
    transmitter_fips: str
    qyyyy: int
    wage: int
    qw_processed_date: str  # YYYYMMDD - when record entered DB
    
    def natural_key(self) -> Tuple[str, str, int]:
        """Unique identifier for this employment record"""
        return (self.ssn, self.fein, self.qyyyy)
    
    def to_fixed_width(self) -> str:
        """Convert to fixed-width QWM record"""
        # Simplified - just the key fields in fixed positions
        parts = [
            "EXP",  # submitter (3)
            "QWM",  # record type (3)
            self.ssn,  # (9)
            "N",  # verification_request (1)
            " " * 55,  # filler1
            self.qw_processed_date,  # (8)
            " " * 62,  # filler2
            "V",  # non_verifiable (1)
            self.fein,  # (9)
            " " * 203,  # filler3
            self.employer_state,  # (2)
            " " * 51,  # filler4
            str(self.wage).zfill(11),  # wage (11)
            str(self.qyyyy).zfill(5),  # reporting period (5)
            " " * 200,  # filler6
            "  ",  # submitted_state_code (2) - blank
            " " * 36,  # filler7
            "R",  # match_code (1)
            "N",  # same_state_data (1)
            " " * 5,  # qw_from_reporting (5) - blank
            " " * 5,  # qw_through_reporting (5) - blank
            " " * 8,  # qw_from_date (8) - blank
            " " * 8,  # qw_through_date (8) - blank
            " " * 28,  # filler8
            " ",  # transmitter_agency (1) - blank
            " " * 8,  # filler9
            self.transmitter_fips,  # (2)
            " " * 271,  # filler10
            "Y",  # pseudo_fein_indicator (1)
        ]
        
        line = "".join(parts)
        assert len(line) == DETAIL_WIDTH, f"Record width {len(line)} != {DETAIL_WIDTH}"
        return line


# ============================================================================
# Core Generation Logic
# ============================================================================

def assign_qw_processed_date(
    qyyyy: int,
    variation_type: str,
    file_dates: List[date],
    rng: random.Random
) -> str:
    """
    Assign when this record was processed into the database.
    
    variation_type:
    - 'baseline': processed soon after quarter end
    - 'late': processed many months after quarter end
    - 'correction': processed recently (for resubmission)
    """
    _, quarter_end = qyyyy_to_dates(qyyyy)
    latest_file = max(file_dates)
    earliest_file = min(file_dates)
    
    if variation_type == 'baseline':
        # Typical: processed 30-90 days after quarter end
        days_after = rng.randint(30, 90)
        processed = quarter_end + timedelta(days=days_after)
        
    elif variation_type == 'late':
        # Late arrival: processed 6-18 months after quarter end
        months_after = rng.randint(6, 18)
        processed = quarter_end + timedelta(days=months_after * 30)
        
    elif variation_type == 'correction':
        # Recent resubmission: processed in last 3 months
        days_before_latest = rng.randint(0, 90)
        processed = latest_file - timedelta(days=days_before_latest)
        
    else:
        processed = quarter_end + timedelta(days=45)
    
    # Clamp to valid range: no future dates, no more than 3 years old
    processed = min(processed, latest_file)
    processed = max(processed, earliest_file - timedelta(days=365*3))
    
    return date_to_str(processed)


def generate_all_records(
    personas: List[Persona],
    quarters: List[int],
    file_dates: List[date],
    rng: random.Random
) -> List[WageRecord]:
    """
    Step 1: Generate ALL baseline records.
    Step 2: Add variation records (late, corrections, duplicates).
    """
    records = []
    
    # STEP 1: Baseline records (every persona × every quarter they're active)
    for p in personas:
        for q in quarters:
            if not persona_active_in_quarter(p, q):
                continue
            
            wage = calculate_wage(p, q)
            proc_date = assign_qw_processed_date(q, 'baseline', file_dates, rng)
            
            records.append(WageRecord(
                ssn=p.ssn,
                fein=p.fein,
                employer_state=p.employer_state,
                transmitter_fips=p.transmitter_fips,
                qyyyy=q,
                wage=wage,
                qw_processed_date=proc_date
            ))
    
    # STEP 2: Add variations
    
    # Late arrivals (~5% of personas, for selected old quarters)
    late_quarters = [q for q in quarters if q <= 42023]
    for p in personas:
        if p.person_id % 20 == 0:  # 5%
            for q in late_quarters[:3]:  # Just a few old quarters
                if persona_active_in_quarter(p, q):
                    wage = calculate_wage(p, q)
                    proc_date = assign_qw_processed_date(q, 'late', file_dates, rng)
                    
                    records.append(WageRecord(
                        p.ssn, p.fein, p.employer_state, p.transmitter_fips,
                        q, wage, proc_date
                    ))
    
    # Corrections/resubmissions (~7% of personas, recent quarters)
    recent_quarters = [q for q in quarters if q >= 22024]
    for p in personas:
        if p.person_id % 15 == 0:  # ~7%
            for q in recent_quarters[:3]:
                if persona_active_in_quarter(p, q):
                    original_wage = calculate_wage(p, q)
                    # Corrected wage (slight difference)
                    corrected_wage = max(0, original_wage + rng.randint(-1000, 1000))
                    proc_date = assign_qw_processed_date(q, 'correction', file_dates, rng)
                    
                    records.append(WageRecord(
                        p.ssn, p.fein, p.employer_state, p.transmitter_fips,
                        q, corrected_wage, proc_date
                    ))
    
    # True duplicates (~1% of all records)
    duplicates = [r for r in records if int(r.ssn) % 100 == 0]
    records.extend(duplicates)
    
    return records


def partition_into_extracts(
    all_records: List[WageRecord],
    extracts: Dict[str, str]
) -> Dict[str, List[WageRecord]]:
    """
    Step 3: Partition records into extract files based on 2-year window.
    
    For each extract, include records where:
        file_date - 2 years <= qw_processed_date <= file_date
    """
    extract_records = {key: [] for key in extracts}
    
    for extract_key, file_date_str in extracts.items():
        file_date = str_to_date(file_date_str)
        window_start = file_date - timedelta(days=365 * 2)
        
        for record in all_records:
            rec_date = str_to_date(record.qw_processed_date)
            
            if window_start <= rec_date <= file_date:
                extract_records[extract_key].append(record)
    
    return extract_records


# ============================================================================
# File Writing
# ============================================================================

def build_header(file_date: str) -> str:
    """Build MTH header record"""
    # Total must equal HEADER_WIDTH (1000)
    # 3 + 3 + 8 + 2 + 8 + 8 = 32, so filler = 968
    parts = [
        "EXP",  # submitter (3)
        "MTH",  # record type (3)
        file_date,  # date_processed (8)
        "  ",  # submitting_state_code (2) - blank
        " " * 8,  # filler1 (8)
        "00000001",  # batch (8)
        " " * 968,  # filler2 (968)
    ]
    line = "".join(parts)
    assert len(line) == HEADER_WIDTH, f"Header width {len(line)} != {HEADER_WIDTH}"
    return line


def build_trailer(qw_count: int) -> str:
    """Build MTT trailer record"""
    # Total must equal TRAILER_WIDTH (1000)
    # 3 + 3 + 11 + 11 + 11 + 11 + 11 = 61, so filler = 939
    total = 1 + qw_count + 1  # header + details + trailer
    
    parts = [
        "EXP",  # submitter (3)
        "MTT",  # record type (3)
        "0" * 11,  # w4_records (11)
        "0" * 11,  # ui_records (11)
        str(qw_count).zfill(11),  # qw_records (11)
        "0" * 11,  # erm_records (11)
        str(total).zfill(11),  # total_records (11)
        " " * 939,  # filler1 (939)
    ]
    line = "".join(parts)
    assert len(line) == TRAILER_WIDTH, f"Trailer width {len(line)} != {TRAILER_WIDTH}"
    return line


def build_filename(file_date: str) -> str:
    """ORG.EXPSXXM1.FPLS.RYYMMDD"""
    yymmdd = file_date[2:]  # 20250615 -> 250615
    return f"ORG.EXPSXXM1.FPLS.R{yymmdd}"


def write_extract_file(
    out_dir: Path,
    file_date: str,
    records: List[WageRecord]
) -> Path:
    """Write one extract file with header + details + trailer"""
    filename = build_filename(file_date)
    filepath = out_dir / filename
    
    with filepath.open('w', encoding='utf-8', newline='\n') as f:
        # Header
        f.write(build_header(file_date) + '\n')
        
        # Details
        for record in records:
            f.write(record.to_fixed_width() + '\n')
        
        # Trailer
        f.write(build_trailer(len(records)) + '\n')
    
    return filepath


def write_manifest(
    out_dir: Path,
    extract_info: Dict[str, Tuple[Path, int]],
    quarters: List[int],
    n_personas: int,
    seed: int
) -> Path:
    """Write README explaining the dataset"""
    manifest = out_dir / "README_demo_qw.md"
    
    lines = [
        "# Demo QW Fixed-Width Dataset\n\n",
        "**This is fake data for demonstration purposes.**\n\n",
        "## Files Generated\n\n",
        "| File | Records | File Date |\n",
        "|------|--------:|-----------|\n",
    ]
    
    for key in sorted(extract_info.keys()):
        filepath, count = extract_info[key]
        file_date = EXTRACTS[key]
        lines.append(f"| `{filepath.name}` | {count:,} | {file_date} |\n")
    
    lines.extend([
        "\n## How This Data Was Generated\n\n",
        "### Step 1: Create all baseline records\n",
        f"- {n_personas} synthetic personas\n",
        f"- Quarters {quarters[0]} through {quarters[-1]}\n",
        "- Each persona × each active quarter = one baseline record\n\n",
        "### Step 2: Assign processing dates\n",
        "- Most records: processed 30-90 days after quarter end\n",
        "- ~5%: late arrivals (processed 6-18 months late)\n",
        "- ~7%: corrections (recent processing date, modified wage)\n",
        "- ~1%: true duplicates (exact copies)\n\n",
        "### Step 3: Partition into extracts\n",
        "- Each extract captures records where:\n",
        "  - `file_date - 2 years ≤ qw_processed_date ≤ file_date`\n",
        "- This creates realistic temporal distributions\n\n",
        "## Key Field Semantics\n\n",
        "- `date_processed` (header): File creation date\n",
        "- `qw_processed_date` (detail): When record entered database\n",
        "- `employer_state`: POSTAL code (XA, XB, etc.)\n",
        "- `transmitter_state_code`: FIPS code (03, 07, etc.)\n",
        "- `qw_reporting_period`: Quarter as QYYYY (e.g., 32023 = Q3 2023)\n\n",
        "## Patterns Demonstrated\n\n",
        "- **Temporal windowing**: 2-year rolling window creates age-skewed distributions\n",
        "- **Late arrivals**: Old quarters appearing in recent extracts\n",
        "- **Corrections**: Same natural key with different wage + recent process date\n",
        "- **Duplicates**: Identical records repeated within extract\n",
        "- **Employment patterns**: Continuous, gaps, late starts\n",
        "- **Zero wages**: Some records legitimately have $0 wages\n\n",
        "## Configuration\n\n",
        f"- Personas: {n_personas}\n",
        f"- Seed: {seed}\n",
        f"- Quarters: {len(quarters)}\n",
    ])

    manifest.write_text("".join(lines), encoding='utf-8')
    return manifest


# ============================================================================
# Main
# ============================================================================

def generate_demo_files(
    out_dir: Path,
    start_qyyyy: int = 32023,
    end_qyyyy: int = 32025,
    n_personas: int = 1200,
    seed: int = 42
) -> Tuple[Dict[str, Tuple[Path, int]], Path]:
    """Generate all demo files and manifest"""
    
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    
    # Setup
    quarters = iter_quarters(start_qyyyy, end_qyyyy)
    personas = create_personas(n_personas, rng)
    file_dates = [str_to_date(d) for d in EXTRACTS.values()]
    
    print(f"Generating {len(personas)} personas across {len(quarters)} quarters...")
    
    # Generate all records
    all_records = generate_all_records(personas, quarters, file_dates, rng)
    print(f"Created {len(all_records):,} total records")
    
    # Partition into extracts
    extract_records = partition_into_extracts(all_records, EXTRACTS)
    
    # Write files
    extract_info = {}
    for key in sorted(EXTRACTS.keys()):
        file_date = EXTRACTS[key]
        records = extract_records[key]
        
        # Shuffle for realism
        rng.shuffle(records)
        
        filepath = write_extract_file(out_dir, file_date, records)
        extract_info[key] = (filepath, len(records))
        
        print(f"  {key}: {filepath.name} ({len(records):,} records)")
    
    # Write manifest
    manifest_path = write_manifest(out_dir, extract_info, quarters, n_personas, seed)
    print(f"\nManifest: {manifest_path.name}")
    
    return extract_info, manifest_path


def main():
    parser = argparse.ArgumentParser(description="Generate demo QW fixed-width files")
    parser.add_argument("--out", default=".", help="Output directory")
    parser.add_argument("--personas", type=int, default=1200, help="Number of personas")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--start", type=int, default=32023, help="Start quarter (QYYYY)")
    parser.add_argument("--end", type=int, default=32025, help="End quarter (QYYYY)")
    
    args = parser.parse_args()
    
    _, _ = generate_demo_files(
        out_dir=Path(args.out),
        start_qyyyy=args.start,
        end_qyyyy=args.end,
        n_personas=args.personas,
        seed=args.seed
    )
    
    print("\n✓ Generation complete")


if __name__ == "__main__":
    main()
