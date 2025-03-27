-- this script reads in fake data to calculate quarterly and annual FRA work outcomes measures for a single jurisdiction
-- fake data made with the fra python module
-- script written in T-SQL for Microsoft SQL Server 2022 (MSSQL)

-- drop and recreate the database
USE master;
IF EXISTS (SELECT name FROM sys.databases WHERE name = 'fra')
BEGIN
    ALTER DATABASE fra SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE fra;
END
CREATE DATABASE fra;
GO

USE fra;
GO

-- drop tables if they exist
IF OBJECT_ID('dbo.exits', 'U') IS NOT NULL DROP TABLE dbo.exits;
IF OBJECT_ID('dbo.earnings', 'U') IS NOT NULL DROP TABLE dbo.earnings;

-- create table for exit reports
CREATE TABLE dbo.exits (
    month INT,
    ssn CHAR(9)
);

-- create table for earnings records
CREATE TABLE dbo.earnings (
    ssn CHAR(9),
    qtr INT,
    earnings INT
);

-- load data from CSV files
BULK INSERT dbo.exits
FROM '\path\to\exiter_report.csv' -- replace
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2, -- skip header
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '\n',
    TABLOCK
);

BULK INSERT dbo.earnings
FROM '\path\to\earnings_records.csv' -- replace
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '\n',
    TABLOCK
);
GO

-- add reporting_quarter column to exits
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'exits' AND COLUMN_NAME = 'reporting_quarter'
)
BEGIN
    ALTER TABLE dbo.exits ADD reporting_quarter INT;
END
GO

-- make reporting_quarter based on month's fiscal year
UPDATE dbo.exits
SET reporting_quarter = 
    CASE
        WHEN (month % 100) IN (10, 11, 12) THEN ((month - (month % 100) + 100) / 10 + 1)
        WHEN (month % 100) IN (1, 2, 3) THEN ((month - (month % 100)) / 10 + 2)
        WHEN (month % 100) IN (4, 5, 6) THEN ((month - (month % 100)) / 10 + 3)
        WHEN (month % 100) IN (7, 8, 9) THEN ((month - (month % 100)) / 10 + 4)
    END;
GO

-- handle placeholder ssns
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'placeholders')
BEGIN
    CREATE TABLE dbo.placeholders (
        month INT,
		ssn NCHAR(9),
        reporting_quarter INT
	);
END
GO

-- move rows where ssn = '999999999' from exits to placeholders
INSERT INTO dbo.placeholders (month, ssn, reporting_quarter)
SELECT month, ssn, reporting_quarter
FROM dbo.exits
WHERE ssn = '999999999';
GO

-- delete placeholders from exits
DELETE FROM dbo.exits
WHERE ssn = '999999999';
GO

-- check on placeholder changes
SELECT COUNT(*) as placeholder_count -- should contain moved rows
FROM dbo.placeholders
GROUP BY reporting_quarter; 
SELECT * FROM dbo.exits WHERE ssn = '999999999'; -- should return 0 rows
GO

-- handling back-to-back months within a single SSN

-- add a ROW_NUMBER to track order within each SSN group
WITH OrderedExits AS (
    SELECT *, 
           ROW_NUMBER() OVER (PARTITION BY ssn ORDER BY month) AS row_num
    FROM dbo.exits
),

-- detect breaks in month sequence
MonthSequence AS (
    SELECT a.*, 
           LAG(month) OVER (PARTITION BY ssn ORDER BY month) AS prev_month,
           CASE 
               WHEN LAG(month) OVER (PARTITION BY ssn ORDER BY month) IS NULL THEN 0
               WHEN (month % 100 = 1 AND LAG(month) OVER (PARTITION BY ssn ORDER BY month) % 100 = 12 
                     AND month / 100 = LAG(month) OVER (PARTITION BY ssn ORDER BY month) / 100 + 1) THEN 1
               WHEN (month = LAG(month) OVER (PARTITION BY ssn ORDER BY month) + 1) THEN 1
               ELSE 0
           END AS is_consecutive
    FROM OrderedExits a
),

-- assign sequence group
SequenceGroups AS (
    SELECT *, 
           SUM(CASE WHEN is_consecutive = 0 THEN 1 ELSE 0 END) 
           OVER (PARTITION BY ssn ORDER BY month ROWS UNBOUNDED PRECEDING) AS sequence_group
    FROM MonthSequence
)

-- keep only the latest observation in each sequence group
SELECT month, reporting_quarter, ssn
INTO #FilteredExits
FROM SequenceGroups
WHERE month = (SELECT MAX(month) 
               FROM SequenceGroups AS sub 
               WHERE sub.ssn = SequenceGroups.ssn 
               AND sub.sequence_group = SequenceGroups.sequence_group);

-- replace original exits table with the filtered version
TRUNCATE TABLE dbo.exits;

INSERT INTO dbo.exits (month, reporting_quarter, ssn)
SELECT month, reporting_quarter, ssn
FROM #FilteredExits;

DROP TABLE #FilteredExits;
GO

SELECT COUNT(*) as records, reporting_quarter
FROM dbo.exits
GROUP BY reporting_quarter
ORDER BY reporting_quarter;

-- quarterly measures (except q2 medians)
WITH DedupExits AS (
    SELECT * FROM (
        SELECT *, 
               ROW_NUMBER() OVER (
                   PARTITION BY ssn, reporting_quarter 
                   ORDER BY month DESC  -- keep the latest month within the quarter
               ) AS row_num
        FROM dbo.exits
    ) AS sub
    WHERE row_num = 1
)
SELECT 
    exits.reporting_quarter,
    COUNT(exits.ssn) AS total_ssns, 

    COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END) AS count_q2_earnings,
    ROUND(
        COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END) * 1.0 / 
        NULLIF(COUNT(exits.ssn), 0), 4
    ) AS rate_q2_employ,

    COUNT(CASE WHEN (COALESCE(e2.earnings, 0) > 0) AND (COALESCE(e4.earnings, 0) > 0) THEN exits.ssn END) AS count_q4_earnings,
    ROUND(
        COUNT(CASE WHEN (COALESCE(e2.earnings, 0) > 0) AND (COALESCE(e4.earnings, 0) > 0) THEN exits.ssn END) * 1.0 / 
        NULLIF(COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END), 0), 4
    ) AS rate_q4_retain
FROM DedupExits AS exits
LEFT JOIN dbo.earnings AS e2
    ON exits.ssn = e2.ssn
    AND e2.qtr = CASE 
        WHEN exits.reporting_quarter % 10 < 3 THEN exits.reporting_quarter + 2
        ELSE exits.reporting_quarter + 8
    END
LEFT JOIN dbo.earnings AS e4
    ON exits.ssn = e4.ssn
    AND e4.qtr = exits.reporting_quarter + 10
GROUP BY exits.reporting_quarter
ORDER BY exits.reporting_quarter;
GO

-- annual measures (except q2 median)
WITH DedupExits AS (
    SELECT * FROM (
        SELECT *, 
               ROW_NUMBER() OVER (
                   PARTITION BY ssn 
                   ORDER BY month DESC  -- keep the latest month within the year
               ) AS row_num
        FROM dbo.exits
    ) AS sub
    WHERE row_num = 1
)
SELECT 
    COUNT(exits.ssn) AS total_ssns, 

    COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END) AS count_q2_earnings,
    ROUND(
        COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END) * 1.0 / 
        NULLIF(COUNT(exits.ssn), 0), 4
    ) AS rate_q2_employ,

    COUNT(CASE WHEN (COALESCE(e2.earnings, 0) > 0) AND (COALESCE(e4.earnings, 0) > 0) THEN exits.ssn END) AS count_q4_earnings,
    ROUND(
        COUNT(CASE WHEN (COALESCE(e2.earnings, 0) > 0) AND (COALESCE(e4.earnings, 0) > 0) THEN exits.ssn END) * 1.0 / 
        NULLIF(COUNT(CASE WHEN COALESCE(e2.earnings, 0) > 0 THEN exits.ssn END), 0), 4
    ) AS rate_q4_retain
FROM DedupExits AS exits
LEFT JOIN dbo.earnings AS e2
    ON exits.ssn = e2.ssn
    AND e2.qtr = CASE 
        WHEN exits.reporting_quarter % 10 < 3 THEN exits.reporting_quarter + 2
        ELSE exits.reporting_quarter + 8
    END
LEFT JOIN dbo.earnings AS e4
    ON exits.ssn = e4.ssn
    AND e4.qtr = exits.reporting_quarter + 10;
GO

-- quarterly medians
WITH DedupExits AS (
    SELECT * FROM (
        SELECT *, 
               ROW_NUMBER() OVER (
                   PARTITION BY ssn, reporting_quarter 
                   ORDER BY month DESC  -- keep the latest month within the quarter
               ) AS row_num
        FROM dbo.exits
    ) AS sub
    WHERE row_num = 1
),
EarningsData AS (
    SELECT 
        exits.reporting_quarter,
        e2.earnings AS q2_earnings
    FROM DedupExits AS exits
    LEFT JOIN dbo.earnings AS e2
        ON exits.ssn = e2.ssn
        AND e2.qtr = CASE 
            WHEN exits.reporting_quarter % 10 < 3 THEN exits.reporting_quarter + 2
            ELSE exits.reporting_quarter + 8
        END
    WHERE e2.earnings > 0 
),
RankedEarnings AS (
    SELECT 
        reporting_quarter,
        q2_earnings,
        ROW_NUMBER() OVER (PARTITION BY reporting_quarter ORDER BY q2_earnings) AS rn_asc,
        COUNT(*) OVER (PARTITION BY reporting_quarter) AS total_count
    FROM EarningsData
),
MedianByQuarter AS (
    SELECT 
        reporting_quarter,
        AVG(q2_earnings * 1.0) AS median_q2_earnings_by_quarter
    FROM RankedEarnings
    WHERE rn_asc IN ( (total_count + 1) / 2, (total_count + 2) / 2 )  -- handles even/odd cases
    GROUP BY reporting_quarter
)
SELECT 
    q.reporting_quarter,
    COUNT(e.q2_earnings) AS num_q2_earners,
    q.median_q2_earnings_by_quarter
FROM MedianByQuarter q
LEFT JOIN EarningsData e ON q.reporting_quarter = e.reporting_quarter
GROUP BY q.reporting_quarter, q.median_q2_earnings_by_quarter
ORDER BY q.reporting_quarter;

-- annual median
WITH DedupExits AS (
    SELECT * FROM (
        SELECT *, 
               ROW_NUMBER() OVER (
                   PARTITION BY ssn 
                   ORDER BY month DESC  -- keep the latest month within year
               ) AS row_num
        FROM dbo.exits
    ) AS sub
    WHERE row_num = 1
),
EarningsData AS (
    SELECT 
        (reporting_quarter / 10) * 10 AS reporting_year,
        e2.earnings AS q2_earnings
    FROM DedupExits AS exits
    LEFT JOIN dbo.earnings AS e2
        ON exits.ssn = e2.ssn
        AND e2.qtr = CASE 
            WHEN exits.reporting_quarter % 10 < 3 THEN exits.reporting_quarter + 2
            ELSE exits.reporting_quarter + 8
        END
    WHERE e2.earnings > 0
),
RankedEarnings AS (
    SELECT 
        reporting_year,
        q2_earnings,
        ROW_NUMBER() OVER (PARTITION BY reporting_year ORDER BY q2_earnings) AS rn_asc,
        COUNT(*) OVER (PARTITION BY reporting_year) AS total_count
    FROM EarningsData
),
MedianByYear AS (
    SELECT 
        reporting_year,
        AVG(q2_earnings * 1.0) AS median_q2_earnings_by_year
    FROM RankedEarnings
    WHERE rn_asc IN ( (total_count + 1) / 2, (total_count + 2) / 2 )  -- handles even/odd cases
    GROUP BY reporting_year
)
SELECT 
    y.reporting_year,
    COUNT(e.q2_earnings) AS num_q2_earners,
    y.median_q2_earnings_by_year
FROM MedianByYear y
LEFT JOIN EarningsData e ON y.reporting_year = e.reporting_year
GROUP BY y.reporting_year, y.median_q2_earnings_by_year
ORDER BY y.reporting_year;
