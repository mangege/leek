# leek
跨交易所套利框架.基于 Python asyncio, CCXT, WebSocket.

* Bootstrap 项目: https://github.com/mangege/mow
* 套利业务逻辑: https://github.com/mangege/leek
* WebSocket 抓取深度数据: https://github.com/mangege/ccxtws

## Troubleshooting

* `poloniex {"error":"Nonce must be greater than 1609057521146. You provided 1609057520910."}`

需要为每个 poloniex 交易所的套利对设置不同的 API Key,这样就可以防止随机数因 asyncio 线程切换而导致提交顺序变了.  
[https://stackoverflow.com/questions/29311124/solutions-for-nonce-error-caused-by-threaded-api-calls](https://stackoverflow.com/questions/29311124/solutions-for-nonce-error-caused-by-threaded-api-calls)
