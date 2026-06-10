# Demo QW Fixed-Width Dataset

**This is fake data for demonstration purposes.**

## Files Generated

| File | Records | File Date |
|------|--------:|-----------|
| `ORG.EXPSXXM1.FPLS.R250615` | 7,890 | 20250615 |
| `ORG.EXPSXXM1.FPLS.R250915` | 9,029 | 20250915 |
| `ORG.EXPSXXM1.FPLS.R260115` | 9,306 | 20260115 |
| `ORG.EXPSXXM1.FPLS.R260315` | 8,582 | 20260315 |

## How This Data Was Generated

### Step 1: Create all baseline records
- 1200 synthetic personas
- Quarters 32023 through 32025
- Each persona × each active quarter = one baseline record

### Step 2: Assign processing dates
- Most records: processed 30-90 days after quarter end
- ~5%: late arrivals (processed 6-18 months late)
- ~7%: corrections (recent processing date, modified wage)
- ~1%: true duplicates (exact copies)

### Step 3: Partition into extracts
- Each extract captures records where:
  - `file_date - 2 years ≤ qw_processed_date ≤ file_date`
- This creates realistic temporal distributions

## Key Field Semantics

- `date_processed` (header): File creation date
- `qw_processed_date` (detail): When record entered database
- `employer_state`: POSTAL code (XA, XB, etc.)
- `transmitter_state_code`: FIPS code (03, 07, etc.)
- `qw_reporting_period`: Quarter as QYYYY (e.g., 32023 = Q3 2023)

## Patterns Demonstrated

- **Temporal windowing**: 2-year rolling window creates age-skewed distributions
- **Late arrivals**: Old quarters appearing in recent extracts
- **Corrections**: Same natural key with different wage + recent process date
- **Duplicates**: Identical records repeated within extract
- **Employment patterns**: Continuous, gaps, late starts
- **Zero wages**: Some records legitimately have $0 wages

## Configuration

- Personas: 1200
- Seed: 42
- Quarters: 9
