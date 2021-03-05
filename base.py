class ArbitrageConfig(object):
    def __init__(self, options={}):
        self.name = options['name']
        self.base_coin = options['base_coin']
        self.quote_coin = options['quote_coin']
        self.symbol = f"{self.base_coin}/{self.quote_coin}"
        self.one_to_two_pure_profit_limit = float(options['one_to_two_pure_profit_limit'])  # exchange1 低买 exchange2 高卖 纯利润限制, 5%
        self.two_to_one_pure_profit_limit = float(options['two_to_one_pure_profit_limit'])  # exchange2 低买 exchange1 高卖 纯利润限制, 5%
        self.min_buy_num_limit_by_quote = options['min_buy_num_limit_by_quote']  # 最小交易币数,有些市场限制了小于此个数会创建订单导致失败
        if self.min_buy_num_limit_by_quote is not None:
            self.min_buy_num_limit_by_quote = float(self.min_buy_num_limit_by_quote)
        self.max_buy_num_limit_by_quote = options['max_buy_num_limit_by_quote']  # 最大交易数,防止单方交易失败导致损失太多
        if self.max_buy_num_limit_by_quote is not None:
            self.max_buy_num_limit_by_quote = float(self.max_buy_num_limit_by_quote)
        self.max_open_order_limit = float(options['max_open_order_limit'])  # 当前挂单数限制,防止异常单太多
        self.base_coin_num = float(options['base_coin_num'])  # 基本币数量,用于计算利润,因数量少会导致转帐手续费占比高
        self.quote_coin_num = float(options['quote_coin_num'])  # 报价币数量
        self.exchange1_api_key = options['exchange1_api_key']  # api key
        self.exchange1_secret = options['exchange1_secret']
        self.exchange1_password = options.get('exchange1_password', None)
        self.exchange1_new_ws = options.get('exchange1_new_ws', None)
        self.exchange2_api_key = options['exchange2_api_key']
        self.exchange2_secret = options['exchange2_secret']
        self.exchange2_password = options.get('exchange2_password', None)
        self.exchange2_new_ws = options.get('exchange2_new_ws', None)
        self.exchange1_id = options['exchange1_id']
        self.exchange2_id = options['exchange2_id']
        self.exchange1_taker_fee = float(options['exchange1_taker_fee'])  # 市场1吃单成交费用, 1% 之类的
        self.exchange2_taker_fee = float(options['exchange2_taker_fee'])
        self.exchange1_withdraw_base_fee = float(options['exchange1_withdraw_base_fee'])  # 提现统一预估一个固定值,而不是百分比
        self.exchange1_withdraw_quote_fee = float(options['exchange1_withdraw_quote_fee'])
        self.exchange2_withdraw_base_fee = float(options['exchange2_withdraw_base_fee'])
        self.exchange2_withdraw_quote_fee = float(options['exchange2_withdraw_quote_fee'])
        self.base_coin_alert_num = float(options['base_coin_alert_num'])  # 基本币余额提醒限制,小于此时提醒
        self.quote_coin_alert_num = float(options['quote_coin_alert_num'])
        self.bisect_coin = options['bisect_coin']  # 计算利润时,是否按照平分币两到个市场计算,还是按一个.如果经常是单边市场,可以设置成 False
        self.enable_transfer = options['enable_transfer']  # 不开启转帐交易,则默认不计算提现费.适合两个市场互相有溢价,或手续费过高
