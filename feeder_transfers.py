import numpy as np
import pandas as pd


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

    return rs