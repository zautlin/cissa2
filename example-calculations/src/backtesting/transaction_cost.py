# pylint: disable=too-few-public-methods
import numpy as np


class TransactionCost:
    '''
    Base class for Transaction Cost modelling (interface)

    The transaction cost models need to have a function named 'calculate_tc'
    '''

    def calculate_tc(self, weight_delta: float):  # pylint: disable=unused-argument
        return NotImplementedError


class ConstantTC(TransactionCost):
    '''
        Transaction cost class

        Currently we only have one type of transaction cost, which is a
        constant cost for all securities, linearly proportional to the active weight.
        '''

    def __init__(self, cost: float):
        self.tc = cost

    def calculate_tc(self, weight_delta: float):
        return np.sum(self.tc * np.abs(weight_delta))


class ParabolicTC(TransactionCost):
    '''
    Parabolic transaction cost class

    The transaction cost is a parabolic function of the active weight.
    '''

    def __init__(self, active_weight_boundary: float):
        self.tc = 1 / (active_weight_boundary ** 2)

    def calculate_tc(self, weight_delta: float):
        return np.sum(self.tc * np.abs(weight_delta) ** 2) / 100


class InverseMarketCapTC(TransactionCost):
    '''
    Transaction cost inverse to the market capitalization

    '''

    def __init__(self):
        self.lower_bound = 0.0001
        self.upper_bound = 0.01

        # Period specific TC, depending on market cap
        self.tc = None

    def calculate_tc(self, weight_delta: float):

        return np.sum(self.tc * np.abs(weight_delta))

    def set_tc(self, benchmark_weights: np.array):

        benchmark_weights = 1 / np.array(benchmark_weights)

        min_cap = np.min(benchmark_weights)
        # Max cap is the maximum value in the array (not inf)
        max_cap = np.max(benchmark_weights[np.isfinite(benchmark_weights)])

        # convert inf to large value
        benchmark_weights = np.where(np.isinf(benchmark_weights), max_cap, benchmark_weights)

        # Apply function to each value in numpy array
        self.tc = np.apply_along_axis(self.market_scaled_tc, 0, benchmark_weights, min_cap, max_cap,
                                      self.lower_bound, self.upper_bound)

    @staticmethod
    def market_scaled_tc(x, min_x, max_x, lower_bound, upper_bound):
        return lower_bound + ((x - min_x) / (max_x - min_x)) * (upper_bound - lower_bound)
