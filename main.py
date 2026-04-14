import os.path

from ddor import *
from gna import *


def feeder_transfers(deficiencies_frame, method='linear',
                     portion=0.2, include_actual=True):

    eligible_cols = list(deficiencies_frame.columns)
    if not include_actual:
        eligible_cols.remove('act')

    rs = deficiencies_frame.copy()
    if method == 'low_quartile':
        for col in eligible_cols:
            s = rs[col]
            nz = s[s != 0]
            if not nz.empty:
                thresh = nz.quantile(portion)
                rs.loc[(s != 0) & (s <= thresh), col] = 0

    elif method == 'random':
        for col in eligible_cols:
            s = rs[col]
            nz_idx = s[s != 0].index
            if len(nz_idx) > 0:
                k = int(portion * len(nz_idx))
                drop_idx = np.random.choice(nz_idx, size=k,
                                            replace=False)
                rs.loc[drop_idx, col] = 0

    else:
        for col in eligible_cols:
            rs[col] = (1-portion) * deficiencies_frame[col]

    # calculating overloads
    overloads_avoided = pd.DataFrame()
    for c in ['net', 'dec', 'inc']:
        overloads_avoided[c] = (rs[c] - rs['act'])

    return rs, overloads_avoided


if __name__ == '__main__':

    acc_folder = 'C:/Users/user1/Documents/LBNL/projects/CPUC Project/LODGE Work/data'
    # 2023 PGE
    data_folder_2023 = os.path.join(
        acc_folder,
        'Confidential- E3 Calculations - 2024 ACC Distribution Data20250403112056'
    )

    pge_ddor_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
    pge_ddor_dict_2023   = 'parser_data/ddor/ddor_2023_pge_parser.csv'
    pge_d = DDOR(utility_name="PG&E",
                 year=2023,
                 file_path=pge_ddor_file_2023,
                 parsing_dictionary=pge_ddor_dict_2023)

    pge_gna_file_2023 = os.path.join(data_folder_2023, 'PG&E_working draft_to_share.xlsx')
    pge_gna_dict_2023 = 'parser_data/gna/gna_2023_pge_parser.csv'
    pge_kl_dict_2023 = 'parser_data/known_loads/kl_2023_pge_parser.csv'

    pge_g = GNA(utility_name="PG&E",
                   year_start=2023, year_end=2027)
    pge_g.add_records(xls_file=pge_gna_file_2023,
                         parsing_csv_file=pge_gna_dict_2023)

    pge_g.add_records(xls_file=pge_gna_file_2023,
                         parsing_csv_file=pge_kl_dict_2023)

    pge_g.get_overloads()
    act = pge_g.actual_overloads
    cf = pge_g.counterfactual_overloads
    dfr = pge_g.deferred_overloads
    der = pge_g.der_totals
    ld = pge_g.actual_load
    net = pge_g.net_load
    inc = pge_g.inc_load
    dec = pge_g.dec_load
    gna_data = pge_g.gna_data

    # getting the piecewise linear function from DDOR
    res_pl = pge_d.deficiency_value_piece_wise_linear(fix=True)

    def marginal (x, lbl):
        if x == 0:
            return 0
        else:
            s, i = 0, 0
            segments = res_pl['segment_bounds']
            n = len(segments)
            while x >= s and s < segments[n-1][1]:
                s = segments[i][1]
                i +=1

            return res_pl[lbl][i-1]

    # take overloads per circuit in the actual and counterfactual scenarios
    act.name = 'act'
    df_original  = pd.DataFrame(act).join(cf)

    # remove feeder transfers
    df, feeder_report = feeder_transfers(df_original, method='linear',
                                         portion=0.2, include_actual=False)

    # calculate the marginal cost of deficiencies as a function of deficiency sizes
    slope, inter = pd.DataFrame(columns=df.columns), pd.DataFrame(columns=df.columns)
    for c in df.columns:
        slope[c] = df[c].apply(marginal, lbl='slopes')
        inter[c] = df[c].apply(marginal, lbl='intercepts')
    marginal_cost = (df * slope + inter)

    # calculate the total cost for all feeder in actual and counterfactual scenarios
    cost = marginal_cost * df
    cost = cost * 0.0832

    avoided_cost = pd.DataFrame()
    for c in ['net','dec','inc']:
        avoided_cost[c] = (cost[c] - cost['act'])

    counterfactual_overloads = pd.DataFrame()
    for c in ['net','dec','inc']:
        counterfactual_overloads[c] = (df[c] - df['act'])


    result_agg = avoided_cost.sum()/(-der).sum()

    result = avoided_cost.abs().div(der.abs()).replace(
        [float('inf'), -float('inf')], 0).fillna(0)

    info = gna_data[['area', 'division', 'facility_type', 'facility_name']]
    rep = info.join(avoided_cost).join(der, rsuffix="_der")

    s = rep.groupby(['division']).sum()
    for c in ['net','dec','inc']:
        s[f'res_{c}'] = s[c].abs() / s[f'{c}_der'].abs()

    s = s[[c for c in s.columns if 'res_' in c]]

    s = info[['facility_name', 'facility_type']].join(df, rsuffix="_def_mw").join(der, rsuffix="_der_mw")

    print(result_agg)