import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from sklearn.linear_model import LinearRegression
import os


class DDOR:
    """
     Represents data container for DDOR data.
     Includes regression function.
     """

    def __init__(self, utility_name, year, file_path, parsing_dictionary):
        """
           Initialize a DDOR data instance.
           Parameters:
               utility_name: name of the utility
               year: year of the DDOR data
               file_path: path to original DDOR Excel file
               parsing_dictionary: a csv file with a parsing dictionary
           """
        self._file_path = file_path
        self._parsing_dict = parsing_dictionary
        self.utility_name = utility_name
        self.year = year
        self.per_project_data = self._parse()
        self.per_ddor_data = self._aggregate_per_ddor()



    def average_deferral_costs(self):

        df = self.per_ddor_data
        total_cost = df['project_cost_kdol'].sum()
        total_deficiencies = df['def_mw'].sum()

        return total_cost/total_deficiencies


    def _aggregate_per_ddor(self):

        df = self.per_project_data
        deficiencies_mw = df.groupby('id')['def_mw'].sum()
        costs_kw = df.groupby('id')['project_cost_kdol'].max()
        df = pd.DataFrame(deficiencies_mw).join(costs_kw)

        df = df.loc[df.def_mw > 0.0]
        df['avoided_def_cost_dol_kw'] = df['project_cost_kdol'] / df['def_mw']

        return df

    def _parse(self):

        # prepare parsing dictionary
        prs = pd.read_csv(self._parsing_dict).dropna()
        prs = prs.set_index('variable')['value']
        sheet_name = prs['sheet_name']
        row_skip = prs['rows_to_skip']
        row_to_stop = prs['row_to_stop'] if 'row_to_stop' in prs.keys() else None
        col_names = [s for s in prs.index if '_col' in str(s)]
        atr_names = [s for s in prs.index if '_atr' in str(s)]
        col = prs.loc[col_names]
        col_map = dict(zip(col.values, col.index.str.split('_col',n=1).str[0]))
        atr = prs.loc[atr_names]
        atr_map = dict(zip(atr.values, atr.index.str.split('_atr',n=1).str[0]))

        # read_file into a dataframe
        kwargs = dict(
            io=self._file_path,
            sheet_name=sheet_name,
            skiprows=int(row_skip)
        )
        if row_to_stop is not None: # add nrows if rows to stop is defined
            kwargs['nrows'] = int(row_to_stop) - int(row_skip)
        df = pd.read_excel(**kwargs)

        # clean spaces before and after
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        # rename columns according to column maps
        df = df.rename(columns=col_map)
        df = df[col_map.values()]
        df = df.loc[df.id.dropna().index]

        # get only the capacity projects
        if 'service' in df.columns:
            df.service = df.service.replace(atr_map)
            df = df.loc[df.service == 'capacity'].copy()

        # get only the cases where deficiency is higher than zero
        df = df.loc[df.def_mw > 0].copy()

        # clean other attributes and data
        if 'project_type' in df.columns:
            df.project_type = df.project_type.replace(atr_map)
        if 'facility_id' in df.columns:
            df.facility_id = df.facility_id.astype(int)
        df = df.reset_index(drop=True)

        return df


    def deficiency_value_piece_wise_linear(self, segments=3, continuous=True, fix=True,
                                           save_plot=True, savepath=""):

        # data gathering
        df = self.per_ddor_data
        y = df['avoided_def_cost_dol_kw'].to_numpy()
        x =  df['def_mw'].to_numpy()
        e3_value = self.average_deferral_costs()
        k = segments

        # ordering set
        order = np.argsort(x)
        x, y = x[order], y[order]
        n = len(x)

        # starting linear regression
        idx_chunks = np.array_split(np.arange(n), k)
        slopes = []
        intercepts = []
        segment_bounds = []

        for i, idx in enumerate(idx_chunks):
            if len(idx) < 2:
                slopes.append(np.nan)
                continue

            xs = x[idx]
            ys = y[idx]

            lr = LinearRegression().fit(xs.reshape(-1, 1), ys)
            m = float(lr.coef_[0])
            b = float(lr.intercept_)
            slopes.append(m)
            intercepts.append(b)

            start_x = float(xs.min())
            end_x = float(xs.max())
            segment_bounds.append((start_x, end_x))

        # fix to make it continuous
        if continuous:
            segment_bounds = []
            prev_seg = 0
            for i in range(k - 1):
                segment = (intercepts[i + 1] - intercepts[i]) / (slopes[i] - slopes[i + 1])
                segment_bounds.append((prev_seg, segment))
                prev_seg = segment
            segment_bounds.append((prev_seg, max(x)))

        regression_results = {"segment_bounds": segment_bounds,
                              "slopes": slopes,
                              "intercepts": intercepts}

        if fix:
            from fix_regression import correct_and_match_average, correct_and_match_average_iteratitve
            #regression_results_1, info1 = correct_and_match_average(regression_results)
            regression_results, info = correct_and_match_average_iteratitve(regression_results, target=e3_value)
            slopes_fixed = regression_results['slopes']
            intercepts_fixed = regression_results['intercepts']
            segment_bounds_fixed = regression_results['segment_bounds']

            lbl_fx = 'Fixed'
        else:
            lbl_fx = ''

        if save_plot:
            # Plotting

            if savepath == "":
                savepath = f"{self.utility_name}_{self.year}_piecewise_linear.png"

            s = np.array([segment_bounds[0][0]] + [b for (_, b) in segment_bounds], dtype=float)
            plt.figure()

            # scatter: light grey, smaller points
            plt.scatter(x, y, s=8, color="lightgrey", alpha=0.6, label="data")
            plt.axhline(
                y=e3_value,
                linestyle="--",
                color="blue",
                linewidth=1.5,
                label="e3_value"
            )

            # linear segments: orange
            for i in range(len(slopes)):
                x_seg = np.linspace(s[i], s[i + 1], n)
                y_seg = slopes[i] * x_seg + intercepts[i]
                plt.plot(x_seg, y_seg, color="orange", label='regression')

            if fix:
                # linear segments: blue
                for i in range(len(slopes)):
                    x_seg = np.linspace(s[i], s[i + 1], n)
                    y_seg = slopes_fixed[i] * x_seg + intercepts_fixed[i]
                    plt.plot(x_seg, y_seg, color="red", label='fixed regression')

            # segment boundaries: dotted grey
            for xi in s:
                plt.axvline(xi, linestyle=":", color="grey", linewidth=1)

            plt.axhline(0)

            plt.xlabel("deficiency (MW)")
            plt.ylabel("k$-need /MW-deficiency")
            plt.title(f"{self.utility_name} {self.year}\n {lbl_fx} {k}-segment piecewise linear regression")
            plt.legend()
            plt.savefig(savepath, dpi=200, bbox_inches="tight")

        return regression_results


if __name__ == '__main__':


    data_folder_2023 = os.path.join(
        os.path.dirname(os.getcwd()),
        'Confidential- E3 Calculations - 2024 ACC Distribution Data20250403112056'
    )

    # 2023 PGE
    pge_ddor_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
    pge_ddor_dict_2023   = 'parser_data/ddor/ddor_2023_pge_parser.csv'
    pge_2023 = DDOR(utility_name="PG&E",
                    year=2023,
                    file_path=pge_ddor_file_2023,
                    parsing_dictionary=pge_ddor_dict_2023)

    print(pge_2023.average_deferral_costs())

    # 2023 SCE
    sce_ddor_file_2023 = os.path.join(data_folder_2023,'SCE_working draft_to_share.xlsx')
    SCE_ddor_dict_2023 = 'parser_data/ddor/ddor_2023_sce_parser.csv'
    sce_2023 = DDOR(utility_name="SCE",
                    year=2023,
                    file_path=sce_ddor_file_2023,
                    parsing_dictionary=SCE_ddor_dict_2023)

    print (sce_2023.average_deferral_costs())

    # 2023 SDGE
    sdge_ddor_file_2023 = os.path.join(data_folder_2023, 'SDG&E_working draft_to_share.xlsx')
    SDGE_ddor_dict_2023 = 'parser_data/ddor/ddor_2023_sdge_parser.csv'
    sdge_2023 = DDOR(utility_name="SDGE",
                    year=2023,
                    file_path=sdge_ddor_file_2023,
                    parsing_dictionary=SDGE_ddor_dict_2023)

    print(sdge_2023.average_deferral_costs())

    ###########
    # 2024 numbers
    ###########

    data_folder = os.path.join(os.path.dirname(os.getcwd()), 'GNAand Known Load data for LBNL20250304085635')

    # 2024 PGE
    pge_ddor_dict_2024 = 'parser_data/ddor/ddor_2024_pge_parser.csv'
    pge_ddor_file_2024 = os.path.join(data_folder,
                                      'PGE_2024_DDOR_Appendix_A.1_Planned Investment_Confidential.xlsx')
    pge = DDOR(utility_name="PG&E", year=2024,
               file_path=pge_ddor_file_2024, parsing_dictionary= pge_ddor_dict_2024)