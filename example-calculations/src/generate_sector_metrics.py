# pylint: disable=eval-used
"""
File to test the other files
"""

import logging
from src.config.parameters import GUID
from src.engine import loaders as ld, calculation as calc


def generate_sector_metrics():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename="scripts/log/basos_log.log")
    inputs = {'identifier': GUID,
              'error_tolerance': 0.8,
              'approach_to_ke': "Floating",
              'beta_rounding': 0.1,
              'risk_premium': 0.05,
              'userid': "anil.gautam",
              'country': "AUS",
              'currency': "AUD",
              "benchmark_return": 0.075,
              'incl_franking': 'Yes',
              'frank_tax_rate': 0.3,
              'value_franking_cr': 0.75,
              "exchange": 'ASX',
              "franking": 1,
              "bondIndex": "GACGB10"
              }

    sector_metrics = calc.calculate_sector_metrics(inputs)
    ld.save_sector_metrics(sector_metrics)
    print("Success!! Sector Metrics Generated.")


if __name__ == "__main__":
    generate_sector_metrics()
    # generate_optimized_forecast()
    # save_optimal_values()
