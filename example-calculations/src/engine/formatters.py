import functools as func
import pandas as pd


def concat_metrics(df_one, df_two, df_three):
    one = pd.concat(df_one)
    two = pd.concat(df_two)
    three = pd.concat(df_three)
    three.reset_index(drop=True, inplace=True)
    three = three.drop_duplicates()
    return one, two, three


def merge_metrics(metrics_list, on):
    l1_metrics = func.reduce(lambda left, right: pd.merge(left, right, how="inner", on=on), metrics_list)
    l1_metrics.drop_duplicates(inplace=True)
    return l1_metrics


def rename_columns(dataframe, interval):
    dataframe.columns = [f"{interval}Y_{col}" for col in dataframe.columns]
    return dataframe
