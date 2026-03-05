# pylint: disable=eval-used
"""
File to test the other files
"""

import logging
from src.config.parameters import GUID
from src.engine import loaders as ld, calculation as calc


def generate_l2_metrics():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename="cissa_log.log")
    identifier = GUID
    inputs = {'identifier': identifier,
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
    l2_metrics = calc.calculate_L2_metrics_async(inputs)
    l2_metrics["fy_year"] = l2_metrics["fy_year"].astype(int)
    l2_metrics = l2_metrics[l2_metrics['fy_year'] > 1999]
    ld.load_L2_metrics_to_db(identifier, inputs['currency'], l2_metrics)
    print("Success!! L2 Metric Generated.")


if __name__ == "__main__":
    generate_l2_metrics()
