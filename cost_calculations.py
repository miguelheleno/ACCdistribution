import pandas as pd
from feeder_transfers import feeder_transfers


def get_unit_cost_of_deficiencies(df, pl_approx):
    """
    :param df: data frame with the deficiencies
    :param pl_approx: (dict) piece-wise linear approximation of deficiencies
    :return: unit cost dataframe
    """

    segments = pl_approx ['segment_bounds']

    def segment_slopes_or_intercepts (x, lbl):
        if x == 0:
            return 0
        else:
            s, i = 0, 0
            n = len(segments)
            while x >= s and s < segments[ n -1][1]:
                s = segments[i][1]
                i +=1
        return pl_approx[lbl][ i -1]

    # calculate the unit cost of deficiencies as a function of deficiency sizes in each scenario
    slope, inter = pd.DataFrame(columns=df.columns), pd.DataFrame(columns=df.columns)
    for c in df.columns:
        slope[c] = df[c].apply(segment_slopes_or_intercepts, lbl='slopes')
        inter[c] = df[c].apply(segment_slopes_or_intercepts, lbl='intercepts')
    unit_cost = (df * slope + inter)

    return unit_cost


def acc_calculations(ddor, gna, utility_marginal_cost_factor=0.082,
                     feeder_transfers_ratio=0.2, assume_transfers_actual=True):

    # run overloads and retrieve information
    results = gna.get_overloads_and_ders()
    act = results['actual_overloads']
    cf = results['counterfactual_overloads']
    der = results['der_totals']
    gna_data = gna.gna_data

    # take overloads per circuit in the actual and counterfactual scenarios
    act.name = 'act'
    df_original = pd.DataFrame(act).join(cf)

    # remove feeder transfers
    df = feeder_transfers(df_original,
                          method='linear',
                          portion=feeder_transfers_ratio,
                          include_actual=assume_transfers_actual)

    # calculate deferred deficiencies in the counterfactual scenario
    deferred_deficiencies = pd.DataFrame()
    for c in ['net', 'dec', 'inc']:
        deferred_deficiencies[c] = (df[c] - df['act'])

    # Piecewise linear approximation of the DDOR results
    res_pl = ddor.deficiency_value_piece_wise_linear(fix=True)

    # calculate unit costs based on the piece-wise linear results
    unit_costs = get_unit_cost_of_deficiencies(df=df, pl_approx=res_pl)

    # calculate the total cost for all feeder in actual and counterfactual scenarios
    cost = unit_costs * df

    # calculate avoided costs by subtracting
    avoided_cost = pd.DataFrame()
    for c in ['net' ,'dec' ,'inc']:
        avoided_cost[c] = (cost[c] - cost['act'])

    ### Calculating Annual Costs and Reporting ####

    # --- E3 results frm ACC 2024
    acc2024_method_cost = deferred_deficiencies.sum() * ddor.average_deferral_costs()
    acc2024_method_cost_yr = acc2024_method_cost * utility_marginal_cost_factor
    acc2024_method_avoided_cost = acc2024_method_cost_yr / (-der).sum()

    # --- new costs
    avoided_cost_yr = avoided_cost * utility_marginal_cost_factor
    avoided_costs_yr_aggregated = avoided_cost_yr.sum() /(-der).sum()

    avoided_costs_yr_disaggregated = avoided_cost_yr.abs().div(
        der.abs()).replace([float('inf'), -float('inf')], 0).fillna(0)

    df_comparison = pd.DataFrame({
        '2024 Methodology': acc2024_method_avoided_cost,
        'New Aggregated': avoided_costs_yr_aggregated,
        'New Disaggregated (Mean)': avoided_costs_yr_disaggregated.mean(),
    })

    print(df_comparison)

    """
    potential re-aggregation
    
    info = gna_data[['area', 'division', 'facility_type', 'facility_name']]
    rep = info.join(avoided_cost).join(der, rsuffix="_der")

    s = rep.groupby(['division']).sum()
    for c in ['net' ,'dec' ,'inc']:
        s[f'res_{c}'] = s[c].abs() / s[f'{c}_der'].abs()

    s = s[[c for c in s.columns if 'res_' in c]]

    s = info[['facility_name', 'facility_type']].join(df, rsuffix="_def_mw").join(der, rsuffix="_der_mw")
    """