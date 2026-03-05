# pylint: disable=eval-used
"""
File to test the other files
"""
import warnings
import logging
import uuid
from src.engine.calculation import calculate_general_metrics
from src.engine import loaders as ld

# os.chdir(ROOT_DIR)
warnings.filterwarnings('ignore')


def generate_l1_metrics():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename="cissa_log.log")
    identifier = str(uuid.uuid4())
    inputs = {'identifier': identifier,
              'error_tolerance': 0.8,
              'approach_to_ke': "Floating",
              'beta_rounding': 0.1,
              'risk_premium': 0.05,
              'userid': "anil.gautam",
              'country': "AUS",
              'currency': "AUD ",
              "benchmark_return": 0.03,
              'incl_franking': 'Yes',
              'frank_tax_rate': 0.3,
              'value_franking_cr': 0.7,
              "exchange": 'ASX',
              "franking": 1,
              "bondIndex": "GACGB10"
              }
    cost_of_eq, l1_metrics = calculate_general_metrics(inputs)
    ld.upload_metrics_to_db(cost_of_eq, inputs, l1_metrics)
    print(f"Success!! Identifier for Current Request: {identifier}")


if __name__ == "__main__":
    generate_l1_metrics()
