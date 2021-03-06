import json
import logging
import smtplib

import time

import datetime
from poloniex import Poloniex
from creds_3 import POLONIEX_API_KEY, POLONIEX_SECRET_KEY, GMAIL_USER, GMAIL_PASSWORD

PAIRS = ['BTC_ETH',
         'BTC_XRP',
         'BTC_LTC',
         'BTC_STR',
         'BTC_DOGE',
         'BTC_BTS',
         'BTC_XMR',
         'BTC_DASH',
         'BTC_MAID',
         'BTC_FCT',
         'BTC_CLAM',
         ]

BUY_ENSURE_COEF = 1.5
CANDLE_PERIOD = 1800
CANDLES_NUM = 3
VOL_COEF = 1
NUM_OF_PAIRS = 4
MIN_PAIRS = 1
TRADE_AMOUNT = 0.08
DEPTH_OF_SELLING_GLASS = 200
STOP_LOSS = 1.05
MIN_VOLUME_TO_TRADE = 5


class Gmail(object):
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.server = 'smtp.gmail.com'
        self.port = 587
        session = smtplib.SMTP(self.server, self.port)
        session.ehlo()
        session.starttls()
        session.ehlo
        session.login(self.email, self.password)
        self.session = session

    def send_message(self, subject, body):
        """ This must be removed """
        headers = [
            "From: " + self.email,
            "Subject: " + subject,
            "To: " + self.email,
            "MIME-Version: 1.0",
            "Content-Type: text/html"]
        headers = "\r\n".join(headers)
        self.session.sendmail(
            self.email,
            self.email,
            headers + "\r\n\r\n" + body)


def create_poloniex_connection():
    polo = Poloniex()
    polo.key = POLONIEX_API_KEY
    polo.secret = POLONIEX_SECRET_KEY
    return polo


def main():
    polo = create_poloniex_connection()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%H:%M:%S',
                        filename='{}log/logger{}.log'.format(PROJECT_PATH,
                                                             time.strftime('%Y_%m_%d', datetime.datetime.now(
                                                             ).timetuple())))
    with open(PROJECT_PATH + 'bot_margin_date.json') as data_file:
        last_bought_date = json.load(data_file)
    positions = polo.getMarginPosition()
    for pair_name, position in positions.items():
        if position['type'] != 'none' and (time.time() - last_bought_date >= CANDLE_PERIOD or
                                                   float(polo.returnTicker()[pair_name]['last']) > STOP_LOSS * float(
                                                   position['basePrice'])):
            polo.closeMarginPosition(pair_name)
            logging.info('Close position of {}'.format(pair_name))
            gm = Gmail(GMAIL_USER, GMAIL_PASSWORD)
            gm.send_message('CLOSE MARGIN POSITION 333', 'Time: {}'.format(datetime.datetime.now()))
    if time.time() - last_bought_date >= CANDLE_PERIOD:
        positions = polo.getMarginPosition()
        for pair_name, position in positions.items():
            if position['type'] != 'none':
                exit()
        pairs_info = []
        for pair in PAIRS:
            candles_data = polo.returnChartData(
                pair, period=CANDLE_PERIOD, start=int(time.time()) - CANDLE_PERIOD * CANDLES_NUM)[:-1]
            data = [
                {'high': float(candle['high']), 'low': float(candle['low']), 'volume': float(candle['volume']),
                 'close': float(candle['close']), 'open': float(candle['open'])}
                for candle in candles_data
            ]
            if data[1]['volume'] > MIN_VOLUME_TO_TRADE and (data[1]['volume'] / data[0]['volume'] + 0.0001) < VOL_COEF:
                pairs_info.append({
                    'name': pair,
                    'coef': data[1]['volume'] / data[0]['volume']
                })
        logging.info('Number of pairs: {}'.format(len(pairs_info)))
        pairs_info = sorted(pairs_info, key=lambda k: k['coef'], reverse=False)[:NUM_OF_PAIRS] if len(
            pairs_info) >= MIN_PAIRS else []
        balances = polo.returnAvailableAccountBalances()['margin']
        current_btc = float(balances['BTC'])
        if len(pairs_info) > 0:
            sell_amount = TRADE_AMOUNT / len(pairs_info) if current_btc > TRADE_AMOUNT else current_btc / len(
                pairs_info)
            for pair_info in pairs_info:
                current_buy_glass = [
                    [float(order[0]), float(order[1]), float(order[0]) * float(order[1])]
                    for order in polo.returnOrderBook(pair_info['name'], depth=DEPTH_OF_SELLING_GLASS)['bids']
                ]
                sum_previous = 0
                order_price = 0
                for order in current_buy_glass:
                    sum_previous += order[2]
                    if sum_previous >= BUY_ENSURE_COEF * sell_amount:
                        order_price = order[0]
                        break
                if order_price:
                    polo.marginSell(pair_info['name'], order_price, sell_amount / order_price, lendingRate=0.01)
                    logging.info('Selling {} for {} BTC'.format(pair_info['name'].split('_')[-1], sell_amount))
                    pair_info['price'] = order_price

                    gm = Gmail(GMAIL_USER, GMAIL_PASSWORD)
                    gm.send_message(
                        'SELL_MARGIN_333', 'Selling {}{} for {} BTC with rate {} at {}'.format(
                            sell_amount / order_price, pair_info['name'].split(
                                '_')[-1], sell_amount, order_price, datetime.datetime.now()))
        with open(PROJECT_PATH + 'bot_margin_date.json', 'w') as f:
            json.dump((int(time.time()) // CANDLE_PERIOD) * CANDLE_PERIOD, f)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.exception('message')
