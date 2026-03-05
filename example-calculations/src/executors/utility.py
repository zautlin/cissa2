import logging
from src.engine import sql


def get_logger():
    log = logging.getLogger(__name__)
    return log


def get_goal_seek_parameters(inputs):
    return sql.get_goal_seek_param(inputs)


def save_goal_seek_output(guid, dataset):
    COLS = ['guid', 'year', 'base_year', 'ticker', 'key', 'value']
    dataset['guid'] = guid
    dataset = dataset[COLS]
    return sql.save_goal_seek_output(dataset)
