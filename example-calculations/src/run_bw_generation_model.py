# pylint: disable=eval-used
"""
File to test the other files
"""

import logging
from src.config.parameters import GUID
from src.engine import optimizer as opt


def generate_optimized_forecast():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename="cissa_log.log")
    param = {
        'country': 'AUS',
        'guid': GUID,
        'start': 2000,
        'end': 2023,
        'conv_horizon': 60}
    algo_dates = opt.run_optimizer(param)
    algo_dates.pivot_table(index="key", columns='year', values='value')
    print("Success!! L2 Metric Generated.")


if __name__ == "__main__":
    inputs = {
        'country': 'AUS',
        'guid': GUID,
        'start': 2000,
        'end': 2023,
        'conv_horizon': 60}
    # execute_goal_seek(inputs)
    generate_optimized_forecast()
    # save_optimal_values()
