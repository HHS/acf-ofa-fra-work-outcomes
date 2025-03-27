'''Classes & functions to create example data and calculations for the Fiscal Responsibility Act (FRA)
    work outcomes measures.'''

import random
import csv
import copy

class FRAData:
    '''Class to create fake data and calculate jurisdiction-level FRA measures for a single
       federal fiscal year.
    '''
    def __init__(self, fiscal_year: int = None,
                 number_people: tuple[int, int, int, int] = None,
                 duplicate_probability: float = None,
                 placeholder_ssn_probability: float = None,
                 employment_rate: tuple[int, int, int, int] = None,
                 retention_rate: tuple[int, int, int, int] = None,
                 pilot: bool = None):

        # validate fiscal_year
        if fiscal_year is None:
            fiscal_year = 2025 # default value
        if fiscal_year < 2025:
            raise ValueError(f'Invalid fiscal year: {fiscal_year}. Must be 2025 or later.')
        self.fiscal_year = fiscal_year

        # validate number_people
        if number_people is None:
            number_people = (100, 100, 100, 100) # default value
        if not (isinstance(number_people, tuple) and len(number_people) == 4):
            raise ValueError('number_people must be a tuple with exactly four elements.')
        if not all(isinstance(n, int) and n > 0 for n in number_people):
            raise ValueError('All elements in number_people must be positive integers.')
        self.number_people = number_people

        # validate duplicate_probability
        if duplicate_probability is None:
            duplicate_probability = 0 # default value
        if not 0 <= duplicate_probability <= 0.05:
            raise ValueError('duplicate_probability must be between 0 and 0.05 (both inclusive).')
        self.duplicate_probability = duplicate_probability

        # validate duplicate_probability
        if placeholder_ssn_probability is None:
            placeholder_ssn_probability = 0 # default value
        if not 0 <= placeholder_ssn_probability <= 0.05:
            raise ValueError('duplicate_probability must be between 0 and 0.05 (both inclusive).')
        self.placeholder_ssn_probability = placeholder_ssn_probability

       # validate employment_rate
        if employment_rate is None:
            employment_rate = (0.6, 0.6, 0.6, 0.6)  # default values
        if not (isinstance(employment_rate, tuple) and len(employment_rate) == 4):
            raise ValueError('employment_rate must be a tuple with exactly four elements.')
        if not all(0 < n <= 1 for n in employment_rate):
            raise ValueError('employment_rate values must be greater than 0 and less than or equal to 1.')
        self.employment_rate = employment_rate

        # validate retention_rate
        if retention_rate is None:
            retention_rate = (0.75, 0.75, 0.75, 0.75) # default values
        if not (isinstance(retention_rate, tuple) and len(retention_rate) == 4):
            raise ValueError('retention_rate must be a tuple with exactly four elements.')
        if not all(0 < n <= 1 for n in retention_rate):
            raise ValueError('retention_rate values must be greater than 0 and less than or equal to 1.')
        self.retention_rate = retention_rate

        # validate pilot
        if pilot is None:
            pilot = False
        if not(isinstance(pilot, bool)):
            raise ValueError('pilot must be either True or False.')
        self.pilot = pilot

        self.month_data = []

        self.quarter_data = []

    @staticmethod
    def _fake_ssn():
        '''Make a Social Security Number: 900XXXXXX'''
        return f"900{''.join(random.choices('0123456789', k = 6))}"

    def exiter_report(self):
        '''Generate a quarterly exiter report from a single jurisdiction & fiscal year'''
        
        all_ssns = set()
        duplicate_pool = set()
        self.month_data = []

        for quarter in range(1, 5):

            placeholder_count = 0
            months = fiscal_lookup[quarter]
            year = self.fiscal_year if quarter > 1 else self.fiscal_year - 1

            num_people = self.number_people[quarter - 1]
            unique_ssns = set()

            while len(unique_ssns) + placeholder_count < num_people: 
                if duplicate_pool and random.random() < self.duplicate_probability:
                    ssn = random.choice(list(duplicate_pool))
                    duplicate_pool.remove(ssn)
                elif random.random() < self.placeholder_ssn_probability:
                    ssn = 999999999
                    placeholder_count += 1
                else:
                    ssn = self._fake_ssn()
                    while ssn in all_ssns:
                        ssn = self._fake_ssn()
                
                unique_ssns.add(ssn)
                all_ssns.add(ssn)
                duplicate_pool.add(ssn)

            if self.pilot is False:
                self.month_data.extend({
                    'month': f'{year}{random.choice(months):02d}',
                    'ssn': ssn,
                } for ssn in unique_ssns)

                if placeholder_count > 0:
                    counter = 0
                    while counter < placeholder_count:
                        self.month_data.append({
                            'month': f'{year}{random.choice(months):02d}',
                            'ssn': 999999999
                        })
                        counter += 1

            else:
                self.month_data.extend({
                    'month': f'{year}{random.choice(months):02d}',
                    'ssn': ssn,
                    'funding': random.choice(['SSP', 'TANF'])
                } for ssn in unique_ssns)

                if placeholder_count > 0:
                    counter = 0
                    while counter < placeholder_count:
                        self.month_data.append({
                            'month': f'{year}{random.choice(months):02d}',
                            'ssn': 999999999,
                            'funding': random.choice(['SSP', 'TANF'])
                        })
                        counter += 1

        return self.month_data

    def earnings_data(self):
        '''Assign reporting/measure quarters and generate employment and earnings data.'''

        self.quarter_data = copy.deepcopy(self.month_data)

        if not self.quarter_data:
            raise ValueError("exiter_report() must be called before earnings_data().")

        # Assign reporting and measure quarters
        for record in self.quarter_data:
            f_year = int(record['month'][:4])
            month = int(record['month'][4:])

            if month > 9:
                f_year += 1

            quarter = next(q for q, months in fiscal_lookup.items() if month in months)

            if quarter < 3:
                qtr_2, fy_2 = quarter + 2, f_year
                qtr_4, fy_4 = quarter, f_year + 1
            else:
                qtr_2, fy_2 = quarter - 2, f_year + 1
                qtr_4, fy_4 = quarter, f_year + 1

            record['qtr_reporting'] = quarter
            record['f_year'] = f_year
            record['qtr_2'] = f'{fy_2}{qtr_2}'
            record['qtr_4'] = f'{fy_4}{qtr_4}'

        # Generate earnings data
        earnings = []
        existing_records = {}  # Dictionary to track records per SSN

        for qtr in range(1, 5):
            qtr_data = [record for record in self.quarter_data if record['qtr_reporting'] == qtr and record['ssn'] != 999999999]
            num_employed = int(len(qtr_data) * self.employment_rate[qtr - 1])
            num_retained = int(num_employed * self.retention_rate[qtr - 1])

            employed_ssns = random.sample([rec['ssn'] for rec in qtr_data], num_employed)
            retained_ssns = set(random.sample(employed_ssns, num_retained))

            for record in qtr_data:
                ssn = record['ssn']

                if ssn in employed_ssns:
                    if ssn not in existing_records:
                        existing_records[ssn] = set()

                    # Add earnings for qtr_2 only if it doesn't exist
                    if record['qtr_2'] not in existing_records[ssn]:
                        earnings.append({
                            'ssn': ssn,
                            'qtr': record['qtr_2'],
                            'earnings': random.randint(1, 9000)
                        })
                        existing_records[ssn].add(record['qtr_2'])

                    # Add earnings for qtr_4 only if it doesn't exist and the person is retained
                    if ssn in retained_ssns and record['qtr_4'] not in existing_records[ssn]:
                        earnings.append({
                            'ssn': ssn,
                            'qtr': record['qtr_4'],
                            'earnings': random.randint(1, 9000)
                        })
                        existing_records[ssn].add(record['qtr_4'])

        return earnings

def save_csv(data, file_name):
    '''Write data to CSV.'''
    with open(file_name, 'w', newline = '', encoding = 'utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, data[0].keys())
        writer.writeheader()
        writer.writerows(data)

fiscal_lookup = {
            1: [10, 11, 12],  # Q1: Oct, Nov, Dec
            2: [1, 2, 3],     # Q2: Jan, Feb, Mar
            3: [4, 5, 6],     # Q3: Apr, May, Jun
            4: [7, 8, 9]      # Q4: Jul, Aug, Sep
    }

if __name__ == "__main__":
    fra = FRAData()

    exit_data = fra.exiter_report()
    earnings_records = fra.earnings_data()

    save_csv(exit_data, 'exiter_report.csv')
    save_csv(earnings_records, 'earnings_records.csv')

    print("Exiter report and earnings records have been successfully generated and saved.")
