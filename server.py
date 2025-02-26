def auth():
    # Kraken KEY & SECRET
    key = ''
    secret = ''
    return key, secret

import asyncio 
import aiohttp
import websockets
import json
import numpy as np
import time
import datetime
import urllib.parse
import hashlib
import hmac
import base64
from functools import partial

# Time format functions
stamp = lambda: int(time.time() * 1000000)
postage_stamp = lambda: int(time.time())
rightNow = lambda: datetime.datetime.fromtimestamp(int(time.time())).strftime('%I:%M:%S')

# Exclude duplicate server
trade_lock = asyncio.Lock()

# Check if order has been filled
def PullVolume(x, txid):
    y = x['result']['open']
    if txid not in y.keys():
        return 'Filled'
    return 'Filling'

# Extract US Dollar balance from Kraken
def USDollar(f):
    async def Fetch(*a, **b):
        resp = await f(*a, **b)
        if 'result' in resp.keys():
            if 'ZUSD' in resp['result'].keys():
                return float(resp['result']['ZUSD'])
        return None
    return Fetch

# Kraken API class with trading functions
class KrakenAPI:

    def __init__(self):
        self.key, self.secret = auth()
        self.rest_url = 'https://api.kraken.com'

    # SHA512/256 & Base64 authenticated function encryption
    def signature(self, urlpath, data):
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()

    # Places trades and fetches balance
    async def communicate(self, session, uri_path, data):
        headers = {}
        headers['API-Key'] = self.key 
        headers['API-Sign'] = self.signature(uri_path, data)             
        async with session.post(self.rest_url + uri_path, headers=headers, data=data) as resp:
            r = await resp.text()
            return json.loads(r)

    # Fetches Balance
    @USDollar
    async def Balance(self, session):
        endpoint = '/0/private/Balance'
        msg = {
            'nonce': stamp()
        }
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Cancels order
    async def CancelOrder(self, session, pair, txid):
        endpoint = '/0/private/CancelOrder'
        msg = {
            'nonce': stamp(),
            'pair': pair,
            'txid': txid
        }
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Places a market buy order
    async def MarketBuy(self, session, pair, volume):
        endpoint = '/0/private/AddOrder'
        msg = {
            'nonce': stamp(),
            'ordertype': 'market',
            'type': 'buy',
            'volume': volume,
            'pair': pair
        }    
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Places a market sell order
    async def MarketSell(self, session, pair, volume):
        endpoint = '/0/private/AddOrder'
        msg = {
            'nonce': stamp(),
            'ordertype': 'market',
            'type': 'sell',
            'volume': volume,
            'pair': pair
        }    
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Places a limit buy order
    async def LimitBuy(self, session, pair, price, volume, cl_ord_id):
        endpoint = '/0/private/AddOrder'
        msg = {
            'nonce':stamp(),
            'ordertype':'limit',
            'type':'buy',
            'price':price,
            'volume':volume,
            'pair':pair,
            'cl_ord_id':cl_ord_id
        }
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Places a limit sell order
    async def LimitSell(self, session, pair, price, volume, cl_ord_id):
        endpoint = '/0/private/AddOrder'
        msg = {
            'nonce':stamp(),
            'ordertype':'limit',
            'type':'sell',
            'price':price,
            'volume':volume,
            'pair':pair,
            'cl_ord_id':cl_ord_id
        }
        resp = await self.communicate(session, endpoint, msg)
        return resp

    # Gets open orders
    async def OpenOrders(self, session, cl_ord_id):
        endpoint = '/0/private/OpenOrders'
        msg = {
            'nonce':stamp(),
            'trades':True,
            'cl_ord_id': cl_ord_id
        }
        resp = await self.communicate(session, endpoint, msg)
        return resp


# Handles the data from Coinbase and Kraken by storing the orderbook and realtime prices
class Data:

    # OrderBook storage elements
    storeCBPrices = []
    cbids = {}
    casks = {}
    storeKrakenPrices = []

    # Highest bid/Lowest ask used in order placement
    khigh_bid = 0
    klow_ask = 0

    # Side of trade: neutral or long
    side = 'neutral'

    # Does not start system until data has been synced
    def syncData(self):
        if len(self.storeCBPrices) > 20 and len(self.storeKrakenPrices) > 2:
            return True
        return False

    # Fetches Last Price from Kraken
    def KrakenPrice(self):
        return self.storeKrakenPrices[-1]

    # Fetches Last Price from Coinbase
    def BitcoinPrice(self):
        return self.storeCBPrices[-1]

    # Computes the moving average of prices
    def BitcoinMovingAverage(self):
        return np.mean(self.storeCBPrices)

    # Computes some technical measures with the limit orderbook
    def BookVWAP(self, depth=50):
        bids = np.array(list(sorted(self.cbids.items(), reverse=True))[:depth])
        asks = np.array(list(sorted(self.casks.items()))[:depth])
        bw = np.sum(bids[:, 0]*bids[:, 1])/np.sum(bids[:, 1])
        aw = np.sum(asks[:, 0]*asks[:, 1])/np.sum(asks[:, 1])
        ratio = (np.sum(bids[:, 1]) - np.sum(asks[:, 1]))/(np.sum(bids[:, 1]) + np.sum(asks[:, 1]))
        bidp = bids[:, 0][::-1]
        bidv = np.cumsum(bids[:, 1])[::-1]
        askp = asks[:, 0]
        askv = np.cumsum(asks[:, 1])
        obook_graph = {'bp':bidp.tolist(), 'bv':bidv.tolist(), 'ap':askp.tolist(), 'av':askv.tolist()}
        return 0.5*(bw + aw), ratio, obook_graph

    # Calculates the RSI
    def BitcoinRSI(self):
        price = self.storeCBPrices
        up = np.sum([i - j for i, j in zip(price[1:],price[:-1]) if i - j >= 0])
        dn = np.sum([abs(i - j) for i, j in zip(price[1:], price[:-1]) if i - j < 0])
        if dn == 0:
            dn = 1
        return 100.0 - 100.0/(1 + (up/dn))

    # Parses data imported from the Kraken websocket
    def PullKraken(self, resp, coinLimit=50):
        price = float(resp[1]['c'][0])
        self.khigh_bid = float(resp[1]['b'][0])
        self.klow_ask = float(resp[1]['a'][0])
        self.storeKrakenPrices.append(price)

        if len(self.storeKrakenPrices) > coinLimit:
            del self.storeKrakenPrices[0]

    # Parses data imported from the Coinbase websocket
    def PullCoinbase(self, resp, coinLimit=50):
        if 'type' in resp.keys():

            # Stores ticker price data
            if resp['type'] == 'ticker':
                price = float(resp['price'])
                self.storeCBPrices.append(price)

            # Stores the initial snapshot of the level2 orderbook
            if resp['type'] == 'snapshot':
                self.cbids = {float(price):float(size) for price, size in resp['bids']}
                self.casks = {float(price):float(size) for price, size in resp['asks']}

            # Updates the stored level2 orderbook
            if resp['type'] == 'l2update':
                for side, price, size in resp['changes']:
                    price, size = float(price), float(size)
                    if side == 'buy':
                        if size == 0:
                            if price in self.cbids.keys():
                                del self.cbids[price]
                        else:
                            self.cbids[price] = size
                    else:
                        if size == 0:
                            if price in self.casks.keys():
                                del self.casks[price]
                        else:
                            self.casks[price] = size

        if len(self.storeCBPrices) > coinLimit:
            del self.storeCBPrices[0]

# Main Trading System Class
class Trader(Data):

    init_side = 'neutral'
    hold_ror = []

    # Initializes URL's along with transaction fees and exit order time limits
    def __init__(self, tx=0.004, exit_trade=2.5):
        self.kraken_url = 'https://api.kraken.com'
        self.kraken_ws_url = 'wss://ws.kraken.com'
        self.cb_ws_url = 'wss://ws-feed.exchange.coinbase.com'
        self.tx = tx
        self.exit_trade = int(60*exit_trade)
        self.cl_ord_id = 'classOf2013-94-95'
        self.volume = 0.00007
        self.log = None
        self.idle = True
        self.aa = 0

    # Runs the entire server in an asynchronus loop
    def ignition(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.client())
    
    # Initial function opened in the server which divides the sockets and strategy into different
    # asynchronus processes
    async def client(self):

        # Creates an asynchronus session which handles both REST and Socket data
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            
            # Trading strategy server which communicates with React.js
            server = await websockets.serve(partial(self.TradingAlgorithm, session=session), '0.0.0.0', 8080)

            # Start tasks for KrakenFeed and CoinbaseFeed
            tasks = [self.KrakenFeed(session), self.CoinbaseFeed(session)]
            
            await asyncio.gather(*tasks)  # Gather tasks instead of using ensure_future
            
            await server.wait_closed()  # Ensures the WebSocket server stays open


    # Kraken WebSocket Feed
    async def KrakenFeed(self, session):
        async with session.ws_connect(self.kraken_ws_url) as client:
            print("Connected To Kraken..........")
            msg = {'event':'subscribe','pair':['XBT/USD'],'subscription':{'name':'ticker'}}
            await client.send_str(json.dumps(msg))
            while True:
                resp = await client.receive()
                resp = json.loads(resp.data)
                
                if type(resp) == list:
                    self.PullKraken(resp)
                    await asyncio.sleep(0.0001)

    # Coinbase WebSocket Feed
    async def CoinbaseFeed(self, session):
        async with session.ws_connect(self.cb_ws_url) as client:
            print("Connected To Coinbase..........")
            msg = {'type':'subscribe','product_ids':['BTC-USD'], 'channels':['ticker', 'level2_batch']}
            await client.send_str(json.dumps(msg))
            while True:
                resp = await client.receive()
                resp = json.loads(resp.data)
                self.PullCoinbase(resp)
                await asyncio.sleep(0.0001)

    # Momentum Trading Strategy Server
    async def TradingAlgorithm(self, ws, session):

        # Ensures no dual connections open
        async with trade_lock:
            print("Trading Strategy has booted.........")
            await ws.send(json.dumps({'type':'log','log':'Kraken Trading Strategy Initialized'}))
            self.log = ws
            tA = postage_stamp()

            volume = 0.00005

            trader = KrakenAPI()

            entryPrice = 0

        
            while True:
                # If data is loaded, it can trade
                if self.syncData():
                    if self.log:

                        # Fetch parameters from other asynchronus processes
                        btc = self.BitcoinPrice()
                        cbwap, ratio, obook = self.BookVWAP()
                        rsi = self.BitcoinRSI()
                        p = self.KrakenPrice()

                        # Always update the React.js front-end plots with the latest orderbook
                        await self.log.send(json.dumps({'type':'book','book':obook}))

                        # Executes a limit sell order once the signals confirm the price may drop
                        if self.side == 'long' and postage_stamp() - tA > 30 and (postage_stamp() - tA > self.exit_trade or (ratio > 0.15 and self.KrakenPrice() > cbwap and self.KrakenPrice() > self.BitcoinPrice())):
                            trade = await trader.LimitSell(session, "XBTUSD", '{0:.1f}'.format(self.klow_ask-0.1), volume, self.cl_ord_id)
                            print(rightNow(), " Close Position: ", trade)
                            log = f'{rightNow()} Close Position: {json.dumps(trade)}'
                            await self.log.send(json.dumps({'type':'log','log':log}))
                            txid = trade['result']['txid'][0]
                            self.side = 'check_fill_exit'
                            tA = postage_stamp()

                        # Passes a heartbeat to the React.js front-end to keep alive the connection
                        if self.side == 'neutral':
                            log = f'Holding {rightNow()}'
                            await self.log.send(json.dumps({'type':'log','log':log}))
                            
                        # Enters a long position if the conditions are met
                        if self.side == 'neutral' and self.KrakenPrice() < self.BookVWAP()[0] and self.BookVWAP()[1] < -0.15:
                            entryPrice = await trader.Balance(session)
                            await asyncio.sleep(1)
                            trade = await trader.LimitBuy(session, "XBTUSD", '{0:.1f}'.format(self.khigh_bid+0.1), volume, self.cl_ord_id)
                            print(rightNow(), " Open Position: ", trade)
                            log = f'{rightNow()} Open Position: {json.dumps(trade)}'
                            await self.log.send(json.dumps({'type':'log','log':log}))
                            txid = trade['result']['txid'][0]
                            self.side = 'check_fill_long'
                            tA = postage_stamp()
                            self.idle = False
                            await asyncio.sleep(3)
                            
                        # This cancels the long order if it takes 8 seconds or longer to load
                        if self.side == 'check_fill_long' and postage_stamp() - tA > 8:
                            cancel = await trader.CancelOrder(session, "XBTUSD", txid)
                            log = f'{rightNow()} Cancelling Order'
                            print(log)
                            await self.log.send(json.dumps({'type':'log', 'log':log}))
                            await asyncio.sleep(1.5)
                            self.side = 'neutral'
                            tA = postage_stamp()
                            self.idle = True

                        # This monitors if the long order has been filled and continues to trade
                        if self.side == 'check_fill_long':
                            fill = await trader.OpenOrders(session, self.cl_ord_id)
                            book = PullVolume(fill, txid)
                            if book == 'Filled':
                                print(rightNow(), " Buy order filled ", self.khigh_bid)
                                log = f'{rightNow()} Buy order filled {self.khigh_bid}'
                                
                                await self.log.send(json.dumps({'type':'log','log':log}))
                                self.side = 'long'
                                tA = postage_stamp()
                                
                            else:
                                print(rightNow(), " Waiting for buy order to fill")
                                log = f'{rightNow()} Waiting for buy order to fill'
                                await self.log.send(json.dumps({'type':'log','log':log}))
                                await asyncio.sleep(2)

                        # This exits the transaction if the limit sell order has been on the book for more than 20 seconds
                        if self.side == 'check_fill_exit' and postage_stamp() - tA > 20:
                            cancel = await trader.CancelOrder(session, "XBTUSD", txid)
                            await asyncio.sleep(1.5)
                            trade = await trader.MarketSell(session, "XBTUSD", volume)
                            self.side = 'neutral'
                            print(rightNow(), " Broke in sell order ", trade, self.khigh_bid)
                            log = f'{rightNow()} Broke in sell order {json.dumps(trade)} {self.khigh_bid}, Pause for a bit'
                            await self.log.send(json.dumps({'type':'log','log':log}))
                            tA = postage_stamp()
                            print("Pause for a bit")
                            exit_balance = await trader.Balance(session)
                            self.hold_ror.append(exit_balance / entryPrice - 1.0)

                            x = list(range(len(self.hold_ror)))
                            msg = {'type':'plot', 'plot':{'x':x, 'y':self.hold_ror}}
                            await ws.send(json.dumps(msg))

                            self.idle = True
                            await asyncio.sleep(3)
                            
                        # This checks to see if limit sell has been filled in order to continue to the next trade
                        if self.side == 'check_fill_exit':
                            fill = await trader.OpenOrders(session, self.cl_ord_id)
                            book = PullVolume(fill, txid)
                            if book == 'Filled':
                                print(rightNow(), " Sell order filled ", self.klow_ask)
                                print("Pause for a bit")
                                log = f'{rightNow()} Sell order filled {self.klow_ask}, Pause for a bit'
                                await self.log.send(json.dumps({'type':'log', 'log':log}))
                                self.idle = True
                                exit_balance = await trader.Balance(session)
                                self.hold_ror.append(exit_balance / entryPrice - 1.0)
                                
                                x = list(range(len(self.hold_ror)))
                                msg = {'type':'plot', 'plot':{'x':x, 'y':self.hold_ror}}
                                await ws.send(json.dumps(msg))

                                await asyncio.sleep(3)
                                
                                self.side = 'neutral'
                            else:
                                print(rightNow(), " Waiting for sell order to fill")
                                log = f'{rightNow()} Waiting for sell order to fill'
                                await self.log.send(json.dumps({'type':'log','log':log}))
                                await asyncio.sleep(2)
                else:        
                    print(len(self.storeKrakenPrices))
                    
                
                await asyncio.sleep(0.0001)

print("System Booted........")
Trader().ignition() # Start Trading System Server
