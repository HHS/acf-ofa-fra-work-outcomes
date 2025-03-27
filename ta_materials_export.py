'''Create a zip file of standalone technical resources.
   Zipped file written to /output - this is an ignored folder.'''

import os
import zipfile
from datetime import datetime

# export directory & zip file name

export_dir = 'output'
zip_file = 'fra_work_outcomes_' + datetime.today().strftime('%Y%m%d') + '.zip'

# files to include in the zip: location & name of files in the zip
include_files = {
    'fra.py': 'fra.py',
    'example_fra_summary.qmd': 'example_fra_summary.qmd',
    'measure_calculation.R': 'measure_calculation.R',
    'measure_calculation.sql': 'measure_calculation.sql',
    'earnings_records.csv': 'earnings_records.csv',
    'exiter_report.csv': 'exiter_report.csv',
    'example_fra_summary.html': 'example_fra_summary.html',
    'ta_README.md': 'README.md'
}

# check export directory exists
os.makedirs(export_dir, exist_ok = True)

# create the zip file - will overwrite anything saved on the same day
zip_path = os.path.join(export_dir, zip_file)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for src, dest in include_files.items():
        if os.path.exists(src):
            zipf.write(src, arcname = dest)
        else:
            print(f'NOTE: {src} is missing - not saved to zip.')

print(f'Exported files saved to {zip_path}')
