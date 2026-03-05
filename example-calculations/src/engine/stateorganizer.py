# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods
class State:
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.optimized_dict = None
        self.inputs = None
        self.parameters = None
        self.pat = None  # This variable will store the state
        self.ep = None
        self.growth_in_equity = None
        self.return_on_equity = None
        self.book_value_equity = None
        self.profit_after_tax = None
        self.equity_free_cash_flow = None
        self.proportion_franked_dividend = None
        self.dividend = None
        self.franking_credits_distributed = None
        self.present_value_factor = None
        self.market_value_equity = None
        self.change_in_equity = None
        self.equity_free_cash_flow_fc = None
        self.value_created = None
        self.economic_profit = None
        self.year = None
        self.ticker = None

    def store_current_state(self, value):
        self.optimized_dict = value
        self.pat = value['pat']  # This variable will store the state
        self.ep = value['ep']
        self.growth_in_equity = value['growth_in_equity']
        self.return_on_equity = value['return_on_equity']
        self.book_value_equity = value['book_value_equity']
        self.profit_after_tax = value['profit_after_tax']
        self.equity_free_cash_flow = value['equity_free_cash_flow']
        self.proportion_franked_dividend = value['proportion_franked_dividend']
        self.dividend = value['dividend']
        self.franking_credits_distributed = value['franking_credits_distributed']
        self.present_value_factor = value['present_value_factor']
        self.market_value_equity = value['market_value_equity']
        self.change_in_equity = value['change_in_equity']
        self.equity_free_cash_flow_fc = value['equity_free_cash_flow_fc']
        self.value_created = value['value_created']
        self.economic_profit = value['economic_profit']
        self.year = value['year']
        self.ticker = value['ticker']

    def get_current_pat(self):
        return self.pat

    def get_ep(self):
        return self.ep

    def get_growth_in_equity(self):
        return self.growth_in_equity

    def get_return_on_equity(self):
        return self.return_on_equity

    def get_book_value_equity(self):
        return self.book_value_equity

    def get_profit_after_tax(self):
        return self.profit_after_tax

    def get_equity_free_cash_flow(self):
        return self.equity_free_cash_flow

    def get_proportion_franked_dividend(self):
        return self.proportion_franked_dividend

    def get_dividend(self):
        return self.dividend

    def get_franking_credits_distributed(self):
        return self.franking_credits_distributed

    def get_present_value_factor(self):
        return self.present_value_factor

    def get_market_value_equity(self):
        return self.market_value_equity

    def get_change_in_equity(self):
        return self.change_in_equity

    def set_current_parameters(self, row):
        self.parameters = row

    def get_current_parameters(self):
        return self.parameters

    def set_current_inputs(self, row):
        self.inputs = row

    def get_current_inputs(self):
        return self.inputs

    def get_equity_free_cash_flow_fc(self):
        return self.equity_free_cash_flow_fc

    def get_value_created(self):
        return self.value_created

    def get_economic_profit(self):
        return self.economic_profit

    def get_year(self):
        return self.year

    def get_ticker(self):
        return self.ticker

    def get_optimized_dict(self):
        return self.optimized_dict
