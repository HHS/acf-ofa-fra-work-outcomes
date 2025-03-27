# FRA Work Outcome Measures Calculation Materials

This repo contains code and documentation to show how the Temporary Assistance for Needy Families (TANF) Fiscal Responsibility Act (FRA) work outcome measures will be calculated.

## Contents

- [example_fra_summary.qmd](example_fra_summary.qmd): Quarto code that generates data using `fra` module, then walks through the calculations in Python. Settings in this code affects the attributes of outputs: data used in rendered document and generated csv files.
- [fra.py](fra.py): `fra` module to generate fake FRA data, both exit reports and earnings data.
- [measure_calculation.R](measure_calculation.R): R code to do the measure calculations and charts from csv files generated with `fra` module.
- [measure_calculation.sql](measure_calculation.sql): SQL code to do the measure calculations from csv files generated with `fra` module. This code snippet has csv file paths flagging that they need to be replaced; this code is intended for external use.
- [ta_materials_export.py](ta_materials_export.py): Code to create a zip file export of select materials for external use. Depends on the outputs from [example_fra_summary.qmd](example_fra_summary.qmd).
- [ta_README.md](ta_README.md): Read-me specifically for the zip file export for external use.

## Outputs ignored by repo

- **earnings_records.csv**: Fake earnings data for individuals in **exiter_report.csv**. This file can be overwritten when either the Quarto code is rendered or the `fra` module is used apart from the Quarto code.
- **exiter_report.csv**: Year's worth of fake exiter reports. This file can be overwritten when either the Quarto code is rendered or the `fra` module is used apart from the Quarto code.
- **example_fra_summary.html**: This is the rendered Quarto document created by [example_fra_summary.qmd](example_fra_summary.qmd).
- **fra_work_outcomes_YYYYMMDD.zip**: Zip file export of materials for external use. Writes locally to the "output folder". The "output" folder is ignored and created by code if it does not exist.

## Disclaimer

The files provided here are for informational purposes only. They are supplied as an example and may not be suitable for all systems, environments, or use cases. Before using any code or data, thoroughly review, test, and adapt it to fit your specific requirements.

## OFA information on FRA

More information on FRA, including these measures, is available here: [https://acf.gov/ofa/law-regulation/tanf-provisions-fra-2023](https://acf.gov/ofa/law-regulation/tanf-provisions-fra-2023).
