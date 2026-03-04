-- Assumes data already loaded into fra_example.exits and fra_example.earnings

SET search_path = fra_example, public;

------------------------------------------------------------
-- 1. Create cleaned exits table (adds reporting_quarter)
------------------------------------------------------------

DROP TABLE IF EXISTS exits_clean;

CREATE TABLE exits_clean AS
SELECT
    month,
    ssn,
    CASE
        WHEN (month % 100) IN (10,11,12) THEN ((month - (month % 100) + 100) / 10 + 1)
        WHEN (month % 100) IN (1,2,3)    THEN ((month - (month % 100)) / 10 + 2)
        WHEN (month % 100) IN (4,5,6)    THEN ((month - (month % 100)) / 10 + 3)
        WHEN (month % 100) IN (7,8,9)    THEN ((month - (month % 100)) / 10 + 4)
    END AS reporting_quarter
FROM exits
WHERE ssn <> '999999999';

-- store placeholders separately
DROP TABLE IF EXISTS placeholders;

CREATE TABLE placeholders AS
SELECT
    month,
    ssn,
    CASE
        WHEN (month % 100) IN (10,11,12) THEN ((month - (month % 100) + 100) / 10 + 1)
        WHEN (month % 100) IN (1,2,3)    THEN ((month - (month % 100)) / 10 + 2)
        WHEN (month % 100) IN (4,5,6)    THEN ((month - (month % 100)) / 10 + 3)
        WHEN (month % 100) IN (7,8,9)    THEN ((month - (month % 100)) / 10 + 4)
    END AS reporting_quarter
FROM exits
WHERE ssn = '999999999';

------------------------------------------------------------
-- 2. Deduplicate consecutive month sequences
------------------------------------------------------------

DROP TABLE IF EXISTS exits_deduped;

CREATE TABLE exits_deduped AS
WITH OrderedExits AS (
    SELECT *,
           LAG(month) OVER (PARTITION BY ssn ORDER BY month) AS prev_month
    FROM exits_clean
),
MonthSequence AS (
    SELECT *,
        CASE
            WHEN prev_month IS NULL THEN 0
            WHEN ((month % 100) = 1
                  AND (prev_month % 100) = 12
                  AND (month / 100) = (prev_month / 100) + 1) THEN 1
            WHEN (month = prev_month + 1) THEN 1
            ELSE 0
        END AS is_consecutive
    FROM OrderedExits
),
SequenceGroups AS (
    SELECT *,
           SUM(CASE WHEN is_consecutive = 0 THEN 1 ELSE 0 END)
           OVER (PARTITION BY ssn ORDER BY month ROWS UNBOUNDED PRECEDING)
           AS sequence_group
    FROM MonthSequence
),
LatestInGroup AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY ssn, sequence_group ORDER BY month DESC) AS rn
    FROM SequenceGroups
)
SELECT month, ssn, reporting_quarter
FROM LatestInGroup
WHERE rn = 1;

------------------------------------------------------------
-- 3. Quarterly Measures
------------------------------------------------------------

DROP TABLE IF EXISTS quarterly_measures;

CREATE TABLE quarterly_measures AS
WITH DedupQuarter AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY ssn, reporting_quarter ORDER BY month DESC) rn
    FROM exits_deduped
)
SELECT
    d.reporting_quarter,
    COUNT(d.ssn) AS total_ssns,

    COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END) AS count_q2_earnings,

    ROUND(
        COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END)::numeric
        / NULLIF(COUNT(d.ssn),0),
        4
    ) AS rate_q2_employ,

    COUNT(CASE
        WHEN COALESCE(e2.earnings,0) > 0
         AND COALESCE(e4.earnings,0) > 0 THEN 1 END
    ) AS count_q4_earnings,

    ROUND(
        COUNT(CASE
            WHEN COALESCE(e2.earnings,0) > 0
             AND COALESCE(e4.earnings,0) > 0 THEN 1 END)::numeric
        / NULLIF(COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END),0),
        4
    ) AS rate_q4_retain

FROM DedupQuarter d
LEFT JOIN earnings e2
    ON d.ssn = e2.ssn
   AND e2.qtr = CASE
        WHEN d.reporting_quarter % 10 < 3 THEN d.reporting_quarter + 2
        ELSE d.reporting_quarter + 8
   END
LEFT JOIN earnings e4
    ON d.ssn = e4.ssn
   AND e4.qtr = d.reporting_quarter + 10
WHERE rn = 1
GROUP BY d.reporting_quarter
ORDER BY d.reporting_quarter;

------------------------------------------------------------
-- 4. Annual Measures
------------------------------------------------------------

DROP TABLE IF EXISTS annual_measures;

CREATE TABLE annual_measures AS
WITH DedupYear AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY ssn ORDER BY month DESC) rn
    FROM exits_deduped
)
SELECT
    COUNT(d.ssn) AS total_ssns,

    COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END) AS count_q2_earnings,

    ROUND(
        COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END)::numeric
        / NULLIF(COUNT(d.ssn),0),
        4
    ) AS rate_q2_employ,

    COUNT(CASE
        WHEN COALESCE(e2.earnings,0) > 0
         AND COALESCE(e4.earnings,0) > 0 THEN 1 END
    ) AS count_q4_earnings,

    ROUND(
        COUNT(CASE
            WHEN COALESCE(e2.earnings,0) > 0
             AND COALESCE(e4.earnings,0) > 0 THEN 1 END)::numeric
        / NULLIF(COUNT(CASE WHEN COALESCE(e2.earnings,0) > 0 THEN 1 END),0),
        4
    ) AS rate_q4_retain

FROM DedupYear d
LEFT JOIN earnings e2
    ON d.ssn = e2.ssn
   AND e2.qtr = CASE
        WHEN d.reporting_quarter % 10 < 3 THEN d.reporting_quarter + 2
        ELSE d.reporting_quarter + 8
   END
LEFT JOIN earnings e4
    ON d.ssn = e4.ssn
   AND e4.qtr = d.reporting_quarter + 10
WHERE rn = 1;

------------------------------------------------------------
-- 5. Quarterly Median
------------------------------------------------------------

DROP TABLE IF EXISTS quarterly_medians;

CREATE TABLE quarterly_medians AS
WITH EarningsData AS (
    SELECT
        q.reporting_quarter,
        e.earnings::numeric AS q2_earnings
    FROM exits_deduped q
    JOIN earnings e
      ON q.ssn = e.ssn
     AND e.qtr = CASE
        WHEN q.reporting_quarter % 10 < 3 THEN q.reporting_quarter + 2
        ELSE q.reporting_quarter + 8
     END
    WHERE e.earnings > 0
)
SELECT
    reporting_quarter,
    COUNT(*) AS num_q2_earners,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY q2_earnings)
        AS median_q2_earnings
FROM EarningsData
GROUP BY reporting_quarter
ORDER BY reporting_quarter;

------------------------------------------------------------
-- 6. Annual Median
------------------------------------------------------------

DROP TABLE IF EXISTS annual_medians;

CREATE TABLE annual_medians AS
WITH EarningsData AS (
    SELECT
        (reporting_quarter / 10) * 10 AS reporting_year,
        e.earnings::numeric AS q2_earnings
    FROM exits_deduped q
    JOIN earnings e
      ON q.ssn = e.ssn
     AND e.qtr = CASE
        WHEN q.reporting_quarter % 10 < 3 THEN q.reporting_quarter + 2
        ELSE q.reporting_quarter + 8
     END
    WHERE e.earnings > 0
)
SELECT
    reporting_year,
    COUNT(*) AS num_q2_earners,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY q2_earnings)
        AS median_q2_earnings
FROM EarningsData
GROUP BY reporting_year
ORDER BY reporting_year;

SELECT * FROM quarterly_measures;
SELECT * FROM annual_measures;
SELECT * FROM quarterly_medians;
SELECT * FROM annual_medians;
