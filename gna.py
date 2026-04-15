import pandas as pd
import os
import numpy as np


class GNA:
    """
     Represents data container for GNA data.
     Includes all data analysis functions.
     """

    def __init__(self, utility_name, year_start, year_end):
        """
           Initialize a Grid Needs Assessment data instance.
           Parameters:
               utility_name: name of the utility
               year: year of the GNA data
               file_path: path to original GNA Excel file
               parsing_dictionary: a csv file with a parsing dictionary
           """

        self.utility_name = utility_name
        self.year_start = year_start
        self.year_end = year_end
        self.years = list(range(year_start, year_end+1))
        self.gna_data = pd.DataFrame()

        self.actual_load = pd.DataFrame()
        self.inc_ders = pd.DataFrame()
        self.dec_ders = pd.DataFrame()

    def add_records(self, xls_file, parsing_csv_file):
        # prepare parsing dictionary
        prs = pd.read_csv( parsing_csv_file).dropna()
        prs = prs.set_index('variable')['value']
        sheet_name = prs['sheet_name']
        row_skip = prs['rows_to_skip']  if 'rows_to_skip' in prs.keys() else 0
        row_to_stop = prs['row_to_stop'] if 'row_to_stop' in prs.keys() else None
        col_to_stop = prs['col_to_stop'] if 'col_to_stop' in prs.keys() else None

        col_names = [s for s in prs.index if '_col' in str(s)]
        col = prs.loc[col_names]
        col_map = dict(zip(col.values, col.index.str.split('_col',n=1).str[0]))

        # read_file into a dataframe
        kwargs = dict(
            io=xls_file,
            sheet_name=sheet_name,
            skiprows=int(row_skip)
        )
        if row_to_stop is not None:  # add nrows if rows to stop is defined
            kwargs['nrows'] = int(row_to_stop) - int(row_skip)
        if col_to_stop is not None:  # stop at column if defined
            kwargs['usecols'] =f'A:{col_to_stop}'
        df = pd.read_excel(**kwargs)

        # clean spaces before and after
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # Rename columns of df by matching mw keys and appending the corresponding year based on occurrence order
         # getting a range of years
        cols_mw = [k for k in col_map.values() if '_mw' in str(k)]
        facility_cols = [k for k, v in col_map.items()
                   if v in cols_mw] # getting the mw columns from col map
        # starting the iterative algorithm to get new MW column names and add a year based on order.
        counts = {k: 0 for k in facility_cols}
        new_cols = {}
        for c in df.columns:
            for k in sorted(facility_cols, key=len, reverse=True):
                if str(c).startswith(k):
                    i = counts[k]
                    if i < len(self.years):
                        new_cols[c] = f"{col_map[k]}_{self.years[i]}"
                        counts[k] += 1
                    break

        # removing the original mw columns from the col map, updating it and slicing df.
        col_map = {k: v for k, v in col_map.items()
                   if k not in facility_cols}
        col_map.update(new_cols)
        df = df.rename(columns=col_map)
        df = df[col_map.values()].copy()

        # writing
        if self.gna_data.empty:
            self.gna_data = df
        else:
            x = self.gna_data.set_index('facility_id')
            df = df.groupby(['facility_id']).sum()
            x = x.join(df, rsuffix='dRoP')
            x = x.drop([c for c in x.columns if 'dRoP' in c], axis=1)
            x = x.fillna(0)
            self.gna_data = x

    def get_overloads_and_ders (self):
        df = self.gna_data

        load_act, load_inc, load_dec, rating = (pd.DataFrame(), pd.DataFrame(),
                                                pd.DataFrame(), pd.DataFrame())
        for yr in self.years:
            y_df = df[[c for c in df.columns if str(yr) in str(c)]]
            load_inc[f'{yr}'] = df[[c for c in y_df if 'inc_' in c]].sum(axis=1)
            load_dec[f'{yr}'] = df[[c for c in y_df if 'dec_' in c]].sum(axis=1)

            load_act[f'{yr}'] = df[[c for c in y_df if 'demand_mw' in c]].sum(axis=1)
            rating[f'{yr}'] = df[[c for c in y_df if 'rating_mw' in c]].sum(axis=1)

        # if equipment rating is given, adjust rating of each facility given [used for SCE for example]
        equipment_rating_cols = [c for c in df if 'equipment_rating_mw' in c]
        if len(equipment_rating_cols) > 0:
            r = df[[c for c in df if 'equipment_rating_mw' in c]].max(axis=1)
            r = r.apply(lambda x: 9999.9 if x==0 else x)
            for c in rating.columns:
                rating[c] = np.minimum(rating[c].values,r.values)

        # calculate loads in all scenarios
        net = load_act - load_dec - load_inc
        dec = load_act - load_dec
        inc = load_act - load_inc

         # calculate counterfactual and actual deficiencies
        counterfactual = pd.DataFrame()
        counterfactual['net'] = net.sub(rating['2023'], axis=0).clip(lower=0).max(axis=1)
        counterfactual['dec'] = dec.sub(rating['2023'], axis=0).clip(lower=0).max(axis=1)
        counterfactual['inc'] = inc.sub(rating['2023'], axis=0).clip(lower=0).max(axis=1)
        actual_def = load_act.sub(rating['2023'], axis=0).clip(lower=0).max(axis=1)
        #actual_def = (load_act - rating).clip(lower=0).max(axis=1)

        der_red = pd.DataFrame()
        der_red['net'] = (load_dec + load_inc).sum(axis=1)
        der_red['dec'] = load_dec.sum(axis=1)
        der_red['inc'] = load_inc.sum(axis=1)

        self.actual_load = load_act
        self.inc_ders = load_inc
        self.dec_ders = load_dec

        result = {'actual_overloads': actual_def,
                  'counterfactual_overloads':counterfactual,
                  'der_totals':der_red,
                  }
        return result


data_folder_2023 = os.path.join(
    os.path.dirname(os.getcwd()),
    'Confidential- E3 Calculations - 2024 ACC Distribution Data20250403112056'
)

"""
pge_gna_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
pge_gna_dict_2023 = 'parser_data/gna/gna_2023_pge_parser.csv'
pge_kl_dict_2023 = 'parser_data/known_loads/kl_2023_pge_parser.csv'
pge_2023 = GNA(utility_name="PG&E",
               year_start=2023,year_end=2027)
pge_2023.add_records(xls_file=pge_gna_file_2023,
                     parsing_csv_file=pge_gna_dict_2023)

pge_2023.add_records(xls_file=pge_gna_file_2023,
                     parsing_csv_file=pge_kl_dict_2023)


actual, counterfactual = pge_2023.get_overloads()

"""


"""
sce_gna_file_2023 = os.path.join(data_folder_2023,'SCE_working draft_to_share.xlsx')
sce_gna_dict_2023   = 'parser_data/gna/gna_2023_sce_parser.csv'

sce_2023 = GNA(utility_name="SCE",
               year_start=2023,year_end=2027)
sce_2023.add_gna_records(xls_file=sce_gna_file_2023,
                         parsing_csv_file=sce_gna_dict_2023)

"""



