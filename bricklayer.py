import asyncio
import ccxtws
from sortedcontainers import SortedDict
from . import logutils
from . import utils

logger = logutils.get_logger('leek-bricklayer')
notifier = utils.get_airbrake_notifier()


class Bricklayer(object):
    def __init__(self, config):
        self.config = config
        exchange1_options = {'apiKey': config.exchange1_api_key, 'secret': config.exchange1_secret}
        if config.exchange1_password is not None:
            exchange1_options['password'] = config.exchange1_password
        self.exchange1 = utils.get_exchange(config.exchange1_id, exchange1_options)
        exchange2_options = {'apiKey': config.exchange2_api_key, 'secret': config.exchange2_secret}
        if config.exchange2_password is not None:
            exchange2_options['password'] = config.exchange2_password
        self.exchange2 = utils.get_exchange(config.exchange2_id, exchange2_options)

        self.exchange1_base_coin_balance = 0.0
        self.exchange1_quote_coin_balance = 0.0
        self.exchange2_base_coin_balance = 0.0
        self.exchange2_quote_coin_balance = 0.0

        # 挂单数
        self.exchange1_open_order_num = 0
        self.exchange2_open_order_num = 0

        # Order book
        # asks 委卖单, bids 委买单
        self.exchange1_asks = SortedDict()
        self.exchange1_bids = SortedDict()
        self.exchange2_asks = SortedDict()
        self.exchange2_bids = SortedDict()

        # balance_alert
        self.exchange1_base_coin_alerted = False
        self.exchange1_quote_coin_alerted = False
        self.exchange2_base_coin_alerted = False
        self.exchange2_quote_coin_alerted = False

        self.api_call_lock = asyncio.Lock()

    async def balance_alert(self):
        if self.exchange1_base_coin_alerted:
            if self.exchange1_base_coin_balance >= self.config.base_coin_alert_num:
                self.exchange1_base_coin_alerted = False
        else:
            if self.exchange1_base_coin_balance < self.config.base_coin_alert_num:
                self.balance_alert_notice(self.exchange1.id, self.config.base_coin, self.exchange1_base_coin_balance)
                self.exchange1_base_coin_alerted = True
        if self.exchange1_quote_coin_alerted:
            if self.exchange1_quote_coin_balance >= self.config.quote_coin_alert_num:
                self.exchange1_quote_coin_alerted = False
        else:
            if self.exchange1_quote_coin_balance < self.config.quote_coin_alert_num:
                self.exchange1_quote_coin_alerted = True
                self.balance_alert_notice(self.exchange1.id, self.config.quote_coin, self.exchange1_quote_coin_balance)
        if self.exchange2_base_coin_alerted:
            if self.exchange2_base_coin_balance >= self.config.base_coin_alert_num:
                self.exchange2_base_coin_alerted = False
        else:
            if self.exchange2_base_coin_balance < self.config.base_coin_alert_num:
                self.balance_alert_notice(self.exchange2.id, self.config.base_coin, self.exchange2_base_coin_balance)
                self.exchange2_base_coin_alerted = True
        if self.exchange2_quote_coin_alerted:
            if self.exchange2_quote_coin_balance >= self.config.quote_coin_alert_num:
                self.exchange2_quote_coin_alerted = False
        else:
            if self.exchange2_quote_coin_balance < self.config.quote_coin_alert_num:
                self.exchange2_quote_coin_alerted = True
                self.balance_alert_notice(self.exchange2.id, self.config.quote_coin, self.exchange2_quote_coin_balance)

    def balance_alert_notice(self, exchange_id, coin_name, num):
        msg = f"{exchange_id} {coin_name} {num} alert, {self.config.name}"
        notice = notifier.build_notice(msg)
        notice['params']['name'] = self.config.name
        notifier.send_notice(notice)

    async def update_balance(self):
        try:
            datas = await asyncio.gather(self.exchange1.fetch_balance(), self.exchange2.fetch_balance())
            data = datas[0]
            if self.config.base_coin in data:
                self.exchange1_base_coin_balance = data[self.config.base_coin]['free']
            else:
                self.exchange1_base_coin_balance = 0.0
            if self.config.quote_coin in data:
                self.exchange1_quote_coin_balance = data[self.config.quote_coin]['free']
            else:
                self.exchange1_quote_coin_balance = 0.0
            data = datas[1]
            if self.config.base_coin in data:
                self.exchange2_base_coin_balance = data[self.config.base_coin]['free']
            else:
                self.exchange2_base_coin_balance = 0.0
            if self.config.quote_coin in data:
                self.exchange2_quote_coin_balance = data[self.config.quote_coin]['free']
            else:
                self.exchange2_quote_coin_balance = 0.0
            kind = f'{self.config.symbol} exchange1 {self.exchange1.id}, exchange2 {self.exchange2.id},'
            logger.debug("%s balance | exchange1_base_coin_balance %s | exchange1_quote_coin_balance %s " +
                         "| exchange2_base_coin_balance %s exchange2_quote_coin_balance %s",
                         kind, self.exchange1_base_coin_balance, self.exchange1_quote_coin_balance,
                         self.exchange2_base_coin_balance, self.exchange2_quote_coin_balance)
        except Exception as e:
            logger.exception(e)

    async def update_open_orders(self):
        try:
            datas = await asyncio.gather(
                self.exchange1.fetch_open_orders(symbol=self.config.symbol), self.exchange2.fetch_open_orders(symbol=self.config.symbol))
            self.exchange1_open_order_num = len(datas[0])
            self.exchange2_open_order_num = len(datas[1])
        except Exception as e:
            logger.exception(e)

    # run one
    async def update_order_book(self):
        self.exchange1_ws = utils.get_exchange_ws(self.exchange1.id)
        self.exchange2_ws = utils.get_exchange_ws(self.exchange2.id)
        self.exchange1_observer = getattr(ccxtws, f'{self.exchange1.id}_observer')(self.exchange1, self.config.symbol, self.exchange1_ws_callback)
        self.exchange2_observer = getattr(ccxtws, f'{self.exchange2.id}_observer')(self.exchange2, self.config.symbol, self.exchange2_ws_callback)
        self.exchange1_ws.subscribe(self.exchange1_observer)
        self.exchange2_ws.subscribe(self.exchange2_observer)

    async def move_brick(self):
        while True:
            if utils.exit_signal:
                print("catch exit_signal")
                break
            await asyncio.sleep(1)
            try:
                await self._buy_low_and_sell_high(self.exchange1, self.exchange1_asks, self.exchange1_bids, self.exchange2, self.exchange2_asks,
                                                  self.exchange2_bids, self.exchange1_quote_coin_balance, self.exchange2_base_coin_balance,
                                                  self.config.one_to_two_pure_profit_limit)
                await self._buy_low_and_sell_high(self.exchange2, self.exchange2_asks, self.exchange2_bids, self.exchange1, self.exchange1_asks,
                                                  self.exchange1_bids, self.exchange2_quote_coin_balance, self.exchange1_base_coin_balance,
                                                  self.config.two_to_one_pure_profit_limit)
            except Exception as e:
                logger.exception(e)
                notice = notifier.build_notice(e)
                notice['params']['name'] = self.config.name
                notifier.send_notice(notice)
                # 接口异常时暂停一小时再试
                await asyncio.sleep(60 * 60)

    async def run(self):
        # load dep data
        await self.exchange1.load_markets()
        await self.exchange2.load_markets()
        self.exchange1.checkRequiredCredentials()
        self.exchange2.checkRequiredCredentials()
        self._check_exchange_api_support(self.exchange1)
        self._check_exchange_api_support(self.exchange2)

        await self.update_balance()
        await self.update_open_orders()

        await self.update_order_book()

        asyncio.create_task(self._timer_tasks())

        # wait order book
        await asyncio.sleep(10)
        await self.move_brick()

    def _check_exchange_api_support(self, exchange):
        api_items = ['fetchBalance', 'fetchOpenOrders', 'createOrder', 'cancelOrder']
        for api_item in api_items:
            if not exchange.has[api_item]:
                raise RuntimeError("{} not support {}".format(exchange.id, api_item))

    async def _timer_tasks(self):
        while True:
            await asyncio.sleep(180)
            try:
                async with self.api_call_lock:
                    await self.update_balance()
                    await self.balance_alert()
                    await self.update_open_orders()
            except Exception as e:
                logger.exception(e)

    def _update_order_book(self, asks, bids, data):
        if data['full']:
            asks.clear()
            bids.clear()
        for item in data['asks']:
            self._update_order_book_dict(asks, item[0], item[1])
        for item in data['bids']:
            self._update_order_book_dict(bids, item[0], item[1])

    def _update_order_book_dict(self, a_dict, price, volume):
        if volume == 0.0:
            try:
                del a_dict[price]
            except KeyError:
                pass
        else:
            a_dict[price] = volume

    def exchange1_ws_callback(self, data):
        self._update_order_book(self.exchange1_asks, self.exchange1_bids, data)

    def exchange2_ws_callback(self, data):
        self._update_order_book(self.exchange2_asks, self.exchange2_bids, data)

    def get_min_buy_num_limit(self, price):
        if price is None:
            return None
        return self.config.min_buy_num_limit_by_quote / price

    def get_max_buy_num_limit(self, price):
        if price is None:
            return None
        return self.config.max_buy_num_limit_by_quote / price

    # ask_exchange 低买市场, ask 比 bid 价低,所以我们是在此市场买
    async def _buy_low_and_sell_high(self, ask_exchange, ask_asks, ask_bids, bid_exchange, bid_asks, bid_bids,
                                     ask_exchange_quote_coin_num, bid_exchange_base_coin_num, pure_profit_limit):
        kind = f'{self.config.symbol} low buy ask_exchange {ask_exchange.id}, sell high bid_exchange {bid_exchange.id},'
        if not ask_asks or not bid_bids:
            logger.debug('%s - ask_asks or bid_bids is null', kind)
            return

        if ask_bids and self.get_last_ask(ask_asks)[0] <= self.get_last_bid(ask_bids)[0]:
            logger.debug('%s - 低价单卖单被同市场已有单购买', kind)
            return
        if bid_asks and self.get_last_ask(bid_asks)[0] <= self.get_last_bid(bid_bids)[0]:
            logger.debug('%s - 高价买单被同市场已有单卖出', kind)
            return

        ask = self.get_best_ask(ask_asks)
        bid = self.get_best_bid(bid_bids)
        if ask[0] >= bid[0]:
            logger.debug('%s - 卖价 %s - 买价 %s | 无溢价存在', kind, ask[0], bid[0])
            return

        premium_rate = (bid[0] - ask[0]) / ask[0]
        logger.debug('%s - 卖价 %s 数量 %s - 买价 %s 数量 %s - 溢价 %s | 有溢价存在', kind, ask[0], ask[1], bid[0], bid[1], premium_rate)

        # 先记录溢价,再检查是否符合交易条件
        if self.exchange1_open_order_num >= self.config.max_open_order_limit:
            logger.debug(f'exchange1_open_order_num {self.exchange1_open_order_num} > {self.config.max_open_order_limit}')
            return
        if self.exchange2_open_order_num >= self.config.max_open_order_limit:
            logger.debug(f'exchange2_open_order_num {self.exchange2_open_order_num} > {self.config.max_open_order_limit}')
            return

        fee_rate = (self.get_cross_exchange_fee_rate(bid[0]) if self.config.enable_transfer else self.get_exchange_fee_rate(bid[0]))
        if premium_rate <= fee_rate:
            logger.debug('%s - 溢价率小于手续费,无套利空间 %s %s', kind, premium_rate, fee_rate)
            return

        pure_profit = premium_rate - fee_rate
        if pure_profit <= pure_profit_limit:
            logger.debug('%s 纯利润小于期望利润限值 %s %s', kind, pure_profit, pure_profit_limit)
            return

        if ask[1] < self.get_min_buy_num_limit(ask[0]) or bid[1] < self.get_min_buy_num_limit(bid[0]):
            logger.debug('%s 单的数量过小', kind)
            return

        min_price = min(ask[0], bid[0])
        min_buy_num_limit = self.get_min_buy_num_limit(min_price)
        max_buy_num = (ask_exchange_quote_coin_num / ask[0]) * 0.97
        max_sell_num = bid_exchange_base_coin_num
        if max_buy_num < min_buy_num_limit:
            logger.debug('%s quote coin %s 的数量过少 %s', kind, self.config.quote_coin, max_buy_num)
            return
        if max_sell_num < min_buy_num_limit:
            logger.debug('%s base coin %s 的数量过少 %s', kind, self.config.base_coin, max_sell_num)
            return

        buy_num = min(ask[1], bid[1], max_buy_num, max_sell_num)
        if buy_num > self.get_max_buy_num_limit(min_price):
            buy_num = self.get_max_buy_num_limit(min_price)

        try:
            async with self.api_call_lock:
                await self._move_brick_trading(kind, ask_exchange, bid_exchange, ask, bid, buy_num, pure_profit)
                await self.update_balance()
        except Exception as e:
            logger.exception(e)
            await self.update_balance()
            raise e

    async def _move_brick_trading(self, kind, ask_exchange, bid_exchange, ask, bid, num, pure_profit):
        ret = await self.new_order(kind, 'buy', ask_exchange, ask[0], num)
        num = ret['filled_num']
        if num <= 0:
            return  # 无成交
        min_price = min(ask[0], bid[0])
        # 66.6 个数量,下单后有可能交易所订单变成 66.0 个,导致后面不满足最低交易金额限制.所以增加 2% 的金额差异用来填平小数差
        if num < (self.get_min_buy_num_limit(min_price) * 0.80):
            # TODO 导致 base coin 一直增加,是否考虑直接市价卖了,但有些市场又不支持市价交易接口
            logger.debug("%s buy_order order_id %s lt limit %s", kind, ret['order_id'], num)
            return

        ret = await self.new_order(kind, 'sell', bid_exchange, bid[0], num)
        num = ret['remaining_num']
        if ret['success']:
            filled_num = ret['filled_num']
            logger.debug('%s 交易成功,name %s buy_num %s 纯利润率 %s 大概利润 %s', kind, self.config.name, filled_num, pure_profit,
                         '{:.32f}'.format(filled_num * ask[0] * pure_profit))
            return
        price = ask[0] + ask[0] * (self.get_exchange_fee_rate(bid[0]) + 0.002)  # 加 0.2%的滑点
        if num < (self.get_min_buy_num_limit(price) * 0.80):
            # TODO 导致 base coin 一直增加,是否考虑直接市价卖了,但有些市场又不支持市价交易接口
            logger.debug("%s sell_order order_id %s lt limit %s", kind, ret['order_id'], num)
            return
        ret = await self.new_order(kind, 'sell', bid_exchange, price, num, False)
        logger.debug("%s stop loss order id %s num %s stop price %s ask price %s", kind, ret['order_id'], num, price, ask[0])
        if ret['success']:
            return
        # TODO 部分成交导致币数变少,所以简单处理,挂到直到成交为止.或人工介入,或市价卖了

    async def new_order(self, kind, trade_type, exchange, price, num, cancel_sell_order=True):
        order = None
        success = False
        logger.debug("%s create_%s_order num %s price %s", kind, trade_type, num, price)
        if trade_type == 'buy':
            order = await exchange.create_limit_buy_order(self.config.symbol, num, price)
        else:
            order = await exchange.create_limit_sell_order(self.config.symbol, num, price)
        logger.debug("%s %s_order resp %s", kind, trade_type, order)

        await asyncio.sleep(1)  # bibox 下单后有时不能马上查询到

        if 'status' not in order:
            order = await self._fetch_order(exchange, order['id'], self.config.symbol, num)
            logger.debug("%s %s_order resp %s", kind, trade_type, order)

        logger.debug("%s %s_order %s filled %s", kind, trade_type, order['id'], order['filled'])
        if order['status'] == 'closed':
            logger.debug("%s %s_order %s status closed", kind, trade_type, order['id'])
            success = True
            return {"success": success, "filled_num": order['filled'], "remaining_num": order['remaining'], "order_id": order['id']}

        for i in range(1, 4):
            await asyncio.sleep(i)
            order = await self._fetch_order(exchange, order['id'], self.config.symbol, num)
            if order['status'] == 'closed':
                logger.debug("%s %s_order %s status closed", kind, trade_type, order['id'])
                success = True
                return {"success": success, "filled_num": order['filled'], "remaining_num": order['remaining'], "order_id": order['id']}
            if i == 3:
                if order['status'] == 'open':
                    if trade_type == 'buy' or cancel_sell_order:
                        resp = await exchange.cancel_order(order['id'], self.config.symbol)
                        logger.debug("%s %s_order %s cancel_order resp %s", kind, trade_type, order['id'], resp)
                        # 有可能存在数值差,刚好已经成交了,但在 ccxt 有些市场不支持获取非 open status 的订单,所以只能取老的值
        return {"success": success, "filled_num": order['filled'], "remaining_num": order['remaining'], "order_id": order['id']}

    async def _fetch_order(self, exchange, order_id, order_symbol, num):
        if exchange.has['fetchOrder']:
            return await exchange.fetch_order(order_id, order_symbol)
        orders = await exchange.fetch_open_orders(symbol=order_symbol)
        orders = [order for order in orders if order['id'] == order_id]
        if len(orders) == 0:
            return {'id': order_id, 'filled': num, 'remaining': 0.0, 'status': 'closed'}
        return orders[0]

    def get_last_ask(self, asks, idx=0):
        # 卖单价越低越靠前
        return asks.peekitem(idx)

    def get_best_ask(self, asks, max_level=5):
        # price ,number
        ask = [0.0, 0.0]
        a_max_level = max_level if max_level <= len(asks) else len(asks)
        for i in range(0, a_max_level):
            a_ask = self.get_last_ask(asks, i)
            ask[0] = a_ask[0]
            ask[1] += a_ask[1]
            if ask[1] >= self.get_min_buy_num_limit(ask[0]):
                break
        return ask

    def get_last_bid(self, bids, idx=-1):
        # 买单价越高越靠后
        return bids.peekitem(idx)

    def get_best_bid(self, bids, max_level=5):
        # price ,number
        bid = [0.0, 0.0]
        a_max_level = max_level if max_level <= len(bids) else len(bids)
        for i in range(1, a_max_level + 1):
            a_bid = self.get_last_bid(bids, -i)
            bid[0] = a_bid[0]
            bid[1] += a_bid[1]
            if bid[1] >= self.get_min_buy_num_limit(bid[0]):
                break
        return bid

    # 不跨交易转帐,交易手续费率, 大概的预估,不是准确的
    def get_exchange_fee_rate(self, quote_price):
        # 吃单费用,两个市场一般币数各一半,所以除以2
        bisect_coin_num = 2 if self.config.bisect_coin else 1
        buy_fee = self.config.base_coin_num / bisect_coin_num * self.config.exchange1_taker_fee * quote_price
        sell_fee = self.config.base_coin_num / bisect_coin_num * self.config.exchange2_taker_fee * quote_price
        return (buy_fee + sell_fee) / (self.config.base_coin_num / bisect_coin_num * quote_price)

    # 跨交易转帐,交易手续费率, 大概的预估,不是准确的
    def get_cross_exchange_fee_rate(self, quote_price):
        # 吃单费用,两个市场一般币数各一半,所以除以2
        bisect_coin_num = 2 if self.config.bisect_coin else 1
        buy_fee = self.config.base_coin_num / bisect_coin_num * self.config.exchange1_taker_fee * quote_price
        sell_fee = self.config.base_coin_num / bisect_coin_num * self.config.exchange2_taker_fee * quote_price
        base_coin_withdraw_fee = max(self.config.exchange1_withdraw_base_fee, self.config.exchange2_withdraw_base_fee) * quote_price
        quote_coin_withdraw_fee = max(self.config.exchange1_withdraw_quote_fee, self.config.exchange2_withdraw_quote_fee)
        return (buy_fee + sell_fee + base_coin_withdraw_fee + quote_coin_withdraw_fee) / (self.config.base_coin_num / bisect_coin_num * quote_price)
