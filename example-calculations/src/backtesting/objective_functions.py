import numpy as np


def sharpe_ratio_objective(p_return, p_risk, transaction_cost=None, weights_delta=None):
    """
    Objective function for sharpe-ratio optimization.
    """
    # If transaction costs are included
    if transaction_cost:
        return - (p_return / p_risk) + (transaction_cost.calculate_tc(weights_delta))

    # Objetive function without transaction costs
    return -p_return / p_risk


def mean_variance_objective(p_return, p_risk, lambda_val=1.0, transaction_cost=None, weights_delta=None):
    """
    Objective function for mean-variance optimization.
    """
    if transaction_cost:
        return - p_return + (lambda_val * (np.power(p_risk, 2))) + (transaction_cost.calculate_tc(weights_delta))

    return - p_return + (lambda_val * (np.power(p_risk, 2)))
