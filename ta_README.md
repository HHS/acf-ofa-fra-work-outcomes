# FRA Measure Calculation Materials

This folder contains code and documentation to show how the Temporary Assistance for Needy Families (TANF) Fiscal Responsibility Act (FRA) work outcome measures will be calculated.

## Contents

- **README.md**: Provides basic details of this folder's contents and code outputs.
- **fra.py**: `fra` module to generate fake FRA data, both exit reports and earnings data.
- **example_fra_summary.qmd**: Quarto code that generates data using `fra` module, then walks through the measure calculations in Python.  Settings in this code affects the attributes of outputs:
  - data used in rendered document (**example_fra_summary.html**); and
  - generated csv files (**exiter_report.csv** and **earnings_records.csv**).
- **example_fra_summary.html**: This is the rendered Quarto document created by **example_fra_summary.qmd**.
- **exiter_report.csv**: Year's worth of fake exiter reports. This file can be overwritten when either the Quarto code is rendered or the `fra` module is used apart from the Quarto code.
- **earnings_records.csv**: Fake earnings data for individuals in **exiter_report.csv**. This file can be overwritten when either the Quarto code is rendered or the `fra` module is used apart from the Quarto code.
- **measure_calculation.R**: R code to do the measure calculations and charts from csv files generated with `fra` module (**exiter_report.csv** and **earnings_records.csv**).
- **measure_calculation.sql**: SQL code to do the measure calculations from csv files generated with `fra` module (**exiter_report.csv** and **earnings_records.csv**).

## Note on data outputs

The data created by the `fra` module will change each time it is used, even if the attributes supplied to the functions do not change. This is because chance, or randomness, is used in multiple ways to compose the data. For example: earnings values are randomly selected from a range of values; the month of exit is randomly assigned; whether an individual SSN is a duplicate, employed, or retained is randomly determined.

## Disclaimer

The files provided here are for informational purposes only. They are supplied as an example and may not be suitable for all systems, environments, or use cases. Before using any code or data, thoroughly review, test, and adapt it to fit your specific requirements.

## OFA information on FRA

More information on FRA, including these measures, is available here: [https://acf.gov/ofa/law-regulation/tanf-provisions-fra-2023](https://acf.gov/ofa/law-regulation/tanf-provisions-fra-2023).
