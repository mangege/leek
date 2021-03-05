import os
import asyncio
import ccxt.async_support as asyncccxt
import ccxt
import ccxtws
import pybrake


exit_signal = False
exit_signal_count = 0


EXCHANGE_WSS = {}
NEW_EXCHANGE_WSS = []


def get_exchange_options(exchange_id):
    options = {}
    api_key = os.environ.get('{}_API_KEY'.format(exchange_id.upper()))
    secret = os.environ.get('{}_SECRET'.format(exchange_id.upper()))
    password = os.environ.get('{}_PASSWORD'.format(exchange_id.upper()), None)
    if api_key and secret:
        options['apiKey'] = api_key
        options['secret'] = secret
        if password is not None:
            options['password'] = password
    return options


def get_exchange(exchange_id, options=None):
    if options is None:
        options = get_exchange_options(exchange_id)
    exchange = None
    if exchange_id in asyncccxt.exchanges:
        exchange = getattr(asyncccxt, exchange_id)(options)
    else:
        raise
    return exchange


def get_exchange_sync(exchange_id, options=None):
    if options is None:
        options = get_exchange_options(exchange_id)
    exchange = None
    if exchange_id in ccxt.exchanges:
        exchange = getattr(ccxt, exchange_id)(options)
    else:
        raise
    return exchange


def get_exchange_ws(exchange_id, newobj=None):
    if newobj:
        exchange_ws = getattr(ccxtws, exchange_id)()
        NEW_EXCHANGE_WSS.append(exchange_ws)
        return exchange_ws
    if exchange_id in EXCHANGE_WSS:
        return EXCHANGE_WSS[exchange_id]
    exchange_ws = getattr(ccxtws, exchange_id)()
    EXCHANGE_WSS[exchange_id] = exchange_ws
    return exchange_ws


async def run_all_exchange_ws():
    await asyncio.sleep(10)
    for exchange_id, exchange_ws in EXCHANGE_WSS.items():
        asyncio.create_task(exchange_ws.run())
    for exchange_ws in NEW_EXCHANGE_WSS:
        asyncio.create_task(exchange_ws.run())


def get_airbrake_notifier():
    return pybrake.Notifier(
        project_id=os.environ.get('AIRBRAKE_PROJECT_ID'),
        project_key=os.environ.get('AIRBRAKE_API_KEY'),
        environment=os.environ.get('AIRBRAKE_ENVIRONMENT', 'development')
    )
