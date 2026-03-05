# pylint: disable=eval-used
"""
File to test the other files
"""

import logging
from src.engine import xls


def upload_data_to_db():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        filename="cissa_log.log")
    xls.upload_bbg_data_to_postgres(execute=True)


if __name__ == "__main__":
    upload_data_to_db()
