-- postgres_01_load_data.sql
-- Load raw CSVs into schema fra_example.
-- Run from the folder that contains the CSVs:
--   psql -v ON_ERROR_STOP=1 -d your_db -f postgres_01_load_data.sql
--
-- Notes:
-- * This script uses psql client-side \copy, so run it from the directory with the CSVs
--   (or replace file names with absolute paths).
-- * On Windows, paths can be 'C:/path/to/file.csv' or use doubled backslashes.
-- * The script is non-destructive by default (doesn't DROP schema).

-- Ensure schema exists and use it
CREATE SCHEMA IF NOT EXISTS fra_example;
SET search_path = fra_example, public;

DROP TABLE IF EXISTS exits;
DROP TABLE IF EXISTS earnings;
DROP TABLE IF EXISTS placeholders;

-- Create raw tables
CREATE TABLE IF NOT EXISTS exits (
    month INT,
    ssn VARCHAR(9)
);

CREATE TABLE IF NOT EXISTS earnings (
    ssn VARCHAR(9),
    qtr INT,
    earnings INT
);

CREATE TABLE IF NOT EXISTS placeholders (
    month INT,
    ssn VARCHAR(9),
    reporting_quarter INT
);

-- Load CSVs (client-side). Must run with psql from the folder containing CSVs
-- Example command:
--   cd path/to/repo
--   psql -v ON_ERROR_STOP=1 -d your_db -f postgres_01_load_data.sql

-- If files are in another directory, use absolute paths:
-- \copy exits(month, ssn) FROM 'C:/full/path/to/exiter_report.csv' WITH (FORMAT csv, HEADER true)

\copy exits(month, ssn) FROM 'exiter_report.csv' WITH (FORMAT csv, HEADER true)
-- show count after loading exits
SELECT 'exits_loaded' AS stage, COUNT(*) AS cnt FROM exits;

\copy earnings(ssn, qtr, earnings) FROM 'earnings_records.csv' WITH (FORMAT csv, HEADER true)
-- show count after loading earnings
SELECT 'earnings_loaded' AS stage, COUNT(*) AS cnt FROM earnings;

-- Optional: show a few sample rows to confirm format
SELECT 'sample_exits' AS note, * FROM exits ORDER BY month, ssn LIMIT 10;
SELECT 'sample_earnings' AS note, * FROM earnings ORDER BY ssn, qtr LIMIT 10;
