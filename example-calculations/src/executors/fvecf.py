# pylint: disable=eval-used
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
from src.executors import utility as util

logger = util.get_logger()


def calculate_fv_ecf_async(df, inputs, interval):
    # results = calculate_fv_ecf(df, inputs, interval)
    # ISSUE WITH PYTHON x* (1+np.nan)^x is a number should be nan

    df = df.assign(scale_by=np.where(df['ke_open'] > 0, 1, 0))
    groups = df.groupby('ticker')
    # Create ThreadPoolExecutor with 4 threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit each group to the executor
        pools = [executor.submit(
            calculate_fv_ecf, group, inputs, interval)
            for name, group in groups]
        results = pd.concat([pool.result() for pool in pools])
        logger.info("Calculate Metrics Async: Successfully Created!!")

        return results


def calculate_fv_ecf_seq(df, inputs, interval):
    df = df.assign(scale_by=np.where(df['ke_open'] > 0, 1, 0))
    results = calculate_fv_ecf(df, inputs, interval)
    return results


def calculate_fv_ecf(group, inputs, interval):
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    initialize(frank_tax_rate, value_franking_cr)
    for seq in range(interval, 0, -1):
        print(f"Sequence No for FV_ECF: {seq}")
        fv_interval = (seq - 1) * (-1)
        power = interval + fv_interval - 1
        initialize(fv_interval)
        if incl_franking == "Yes":
            group[f'TEMP_FV_ECF_{-1 * fv_interval}_Y'] = (
                    (-1 * group['dividend'].shift(fv_interval)
                     + group['non_div_ecf'].shift(fv_interval)
                     - ((group['dividend'].shift(fv_interval) / (1 - frank_tax_rate))
                        * frank_tax_rate * value_franking_cr * group['franking'].shift(fv_interval)))
                    * np.power((1 + group['ke_open']), power) * group['scale_by'])
        else:
            group[f'TEMP_FV_ECF_{-1 * fv_interval}_Y'] = (group['dividend']
                                                          + group['non_div_ecf']) * np.power(
                (1 + group['ke_open']), fv_interval) * group['scale_by']
    group['FV_ECF_Y'] = group.filter(regex='TEMP_FV_ECF').sum(1).shift(interval-1)
    group['FV_ECF_TYPE'] = f'{interval}Y_FV_ECF'
    group = group.drop(group.filter(regex='TEMP_FV_ECF').columns, axis=1)
    group = group.filter(regex='fy_year|ticker|fx_currency|ECF')
    return group


def initialize(*args):
    return args
