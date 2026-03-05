import pandas as pd


def calc_brinson_by_month(data: pd.DataFrame) -> pd.DataFrame:
    '''
    This function calculates brinson attribution for a given month
    :param data (pandas.DataFrame):
    :return (pandas.DataFrame):
    '''

    grps = data.groupby(['Sector'])

    def aggs_by_grp(x: pd.DataFrame, por_wts_col: str, bm_wts_col: str, rets_col: str):

        x[rets_col] = x[rets_col].fillna(x[rets_col].median())

        bm_wt = x[bm_wts_col].sum()
        por_wt = x[por_wts_col].sum()

        bm_ret = x[rets_col].dot(x[bm_wts_col] / bm_wt)
        por_ret = x[rets_col].dot(x[por_wts_col] / por_wt)

        bm_cont = bm_wt * bm_ret
        allocation = (por_wt - bm_wt) * bm_ret
        selection = (por_ret - bm_ret) * bm_wt
        interaction = (por_wt - bm_wt) * (por_ret - bm_ret)

        selection_cln = 0 if pd.isnull(selection) else selection
        interaction_cln = 0 if pd.isnull(interaction) else interaction

        return pd.Series({'por_wt': por_wt,
                          'bm_wt': bm_wt,
                          'act_wt': por_wt - bm_wt,
                          'por_ret': por_ret,
                          'bm_ret': bm_ret,
                          'bm_cont': bm_cont,
                          'allocation': allocation,
                          'selection': selection_cln,
                          'interaction': interaction_cln,
                          'selection_and_interaction': selection_cln + interaction_cln,
                          'total': allocation + selection_cln + interaction_cln})

    aggs = grps.apply(lambda x: aggs_by_grp(x, 'por_weights', 'bm_weights', 'Returns'))
    return aggs
