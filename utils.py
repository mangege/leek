import os
import ccxt.async_support as ccxt
import ccxtws
import pybrake


exit_signal = False
exit_signal_count = 0


EXCHANGE_WSS = {}


def get_exchange_options(exchange_id):
    options = {}
    api_key = os.environ.get('{}_API_KEY'.format(exchange_id.upper()))
    secret = os.environ.get('{}_SECRET'.format(exchange_id.upper()))
    if api_key and secret:
        options['apiKey'] = api_key
        options['secret'] = secret
    return options


def get_exchange(exchange_id, options=None):
    if options is None:
        options = get_exchange_options(exchange_id)
    exchange = None
    if exchange_id in ccxt.exchanges:
        exchange = getattr(ccxt, exchange_id)(options)
    else:
        raise
    return exchange


def get_exchange_ws(exchange_id):
    if exchange_id in EXCHANGE_WSS:
        return EXCHANGE_WSS[exchange_id]
    exchange_ws = getattr(ccxtws, exchange_id)()
    EXCHANGE_WSS[exchange_id] = exchange_ws
    return exchange_ws


def get_airbrake_notifier():
    return pybrake.Notifier(
        project_id=os.environ.get('AIRBRAKE_PROJECT_ID'),
        project_key=os.environ.get('AIRBRAKE_API_KEY'),
        environment=os.environ.get('AIRBRAKE_ENVIRONMENT', 'development')
    )
