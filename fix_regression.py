import numpy as np

def average_piecewise_y(regression_results):
    bounds = regression_results["segment_bounds"]
    slopes = regression_results["slopes"]
    intercepts = regression_results["intercepts"]

    total_area = 0.0
    x_min = bounds[0][0]
    x_max = bounds[-1][1]

    for (x0, x1), m, b in zip(bounds, slopes, intercepts):
        area = 0.5 * m * (x1**2 - x0**2) + b * (x1 - x0)
        total_area += area

    return total_area / (x_max - x_min)


def fix_piecewise_uc_continuous(regression_results, eps=0.0):
    """
    Fix a piecewise-linear unit-cost function so that:

    1) UC(Q) is continuous across segments
    2) C(Q) = Q * UC(Q) is nondecreasing inside each segment

    Assumes each segment k is:
        UC_k(Q) = m_k * Q + b_k
    over bounds[k] = (q_left, q_right)
    """
    bounds = list(regression_results["segment_bounds"])
    slopes = list(regression_results["slopes"])
    intercepts = list(regression_results["intercepts"])

    new_slopes = slopes.copy()
    new_intercepts = intercepts.copy()

    def uc(m, b, q):
        return m * q + b

    def min_allowed_slope(uc_left, q_left, q_right, eps=0.0):
        denom = 2.0 * q_right - q_left
        return (eps - uc_left) / denom

    # First segment
    q_left, q_right = bounds[0]
    m = slopes[0]
    b = intercepts[0]

    uc_left = uc(m, b, q_left)
    m_lb = min_allowed_slope(uc_left, q_left, q_right, eps=eps)
    if m < m_lb:
        m = m_lb

    b = uc_left - m * q_left
    new_slopes[0] = m
    new_intercepts[0] = b

    # Remaining segments
    for k in range(1, len(bounds)):
        q_left, q_right = bounds[k]

        m_prev = new_slopes[k - 1]
        b_prev = new_intercepts[k - 1]
        uc_left = uc(m_prev, b_prev, q_left)

        m = slopes[k]
        m_lb = min_allowed_slope(uc_left, q_left, q_right, eps=eps)
        if m < m_lb:
            m = m_lb

        b = uc_left - m * q_left

        new_slopes[k] = m
        new_intercepts[k] = b

    return {
        "segment_bounds": bounds,
        "slopes": new_slopes,
        "intercepts": new_intercepts,
    }


def shift_intercepts(regression_results, shift):
    """
    Apply UC(Q) -> UC(Q) - shift.
    Since UC is linear by segment, this only changes intercepts.
    """
    return {
        "segment_bounds": list(regression_results["segment_bounds"]),
        "slopes": list(regression_results["slopes"]),
        "intercepts": [b - shift for b in regression_results["intercepts"]],
    }


def correct_and_match_average(regression_results_original):
    """
    Step 1: correct the original function
    Step 2: compute average shift S = y2 - y1
    Step 3: shift intercepts down by S
    Step 4: correct again

    Returns
    -------
    regression_results_final : dict
    info : dict with y1, y2, S, y3
    """
    y1 = average_piecewise_y(regression_results_original)

    regression_results_corr = fix_piecewise_uc_continuous(regression_results_original)
    y2 = average_piecewise_y(regression_results_corr)

    S = y2 - y1

    regression_results_shifted = shift_intercepts(regression_results_corr, S)
    regression_results_final = fix_piecewise_uc_continuous(regression_results_shifted)

    y3 = average_piecewise_y(regression_results_final)

    info = {
        "y1_original_average": y1,
        "y2_corrected_average": y2,
        "S_shift_applied": S,
        "y3_final_average": y3,
    }

    return regression_results_final, info


def correct_and_match_average_iteratitve(
    regression_results_original, target=None,
    tol=1e-6,
    max_iter=100,
):
    """
    Iteratively find a downward shift S on UC(Q) so that, after re-correction,
    the final average matches the original average.

    Procedure
    ---------
    1) Correct the original function once
    2) Search for S such that:
           average_piecewise_y(
               fix_piecewise_uc_continuous(
                   shift_intercepts(corrected_function, S)
               )
           ) == average_piecewise_y(original_function)

    Uses bisection on S.

    Returns
    -------
    regression_results_final : dict
    info : dict with y1, y2, S, y3, iterations, converged
    """
    if target is None:
        y1 = average_piecewise_y(regression_results_original)
    else:
        y1 = target

    regression_results_corr = fix_piecewise_uc_continuous(regression_results_original)
    y2 = average_piecewise_y(regression_results_corr)

    def final_average_given_shift(S):
        shifted = shift_intercepts(regression_results_corr, S)
        repaired = fix_piecewise_uc_continuous(shifted)
        y_final = average_piecewise_y(repaired)
        return y_final, repaired

    # No need to search if already matched
    if abs(y2 - y1) <= tol:
        info = {
            "y1_original_average": y1,
            "y2_corrected_average": y2,
            "S_shift_applied": 0.0,
            "y3_final_average": y2,
            "iterations": 0,
            "converged": True,
        }
        return regression_results_corr, info

    # Lower bound: no shift
    S_low = 0.0
    y_low, reg_low = final_average_given_shift(S_low)
    f_low = y_low - y1

    # Initial upper bound: one-pass shift
    S_high = max(y2 - y1, 1e-12)
    y_high, reg_high = final_average_given_shift(S_high)
    f_high = y_high - y1

    # Expand upper bound until the root is bracketed
    expand_count = 0
    while f_low * f_high > 0 and expand_count < max_iter:
        S_high *= 2.0
        y_high, reg_high = final_average_given_shift(S_high)
        f_high = y_high - y1
        expand_count += 1

    if f_low * f_high > 0:
        info = {
            "y1_original_average": y1,
            "y2_corrected_average": y2,
            "S_shift_applied": S_high,
            "y3_final_average": y_high,
            "iterations": expand_count,
            "converged": False,
        }
        return reg_high, info

    # Bisection
    regression_results_final = reg_high
    y3 = y_high
    converged = False
    iterations = 0

    for iterations in range(1, max_iter + 1):
        S_mid = 0.5 * (S_low + S_high)
        y_mid, reg_mid = final_average_given_shift(S_mid)
        f_mid = y_mid - y1

        if abs(f_mid) <= tol:
            regression_results_final = reg_mid
            y3 = y_mid
            converged = True
            S_star = S_mid
            break

        if f_low * f_mid <= 0:
            S_high = S_mid
            f_high = f_mid
        else:
            S_low = S_mid
            f_low = f_mid

        regression_results_final = reg_mid
        y3 = y_mid
        S_star = S_mid

    info = {
        "y1_original_average": y1,
        "y2_corrected_average": y2,
        "S_shift_applied": S_star,
        "y3_final_average": y3,
        "iterations": iterations,
        "converged": converged,
    }

    return regression_results_final, info