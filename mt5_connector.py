"""
MT5 auto-detection and order execution.
Connects to the already-running MT5 terminal — no credentials needed.
"""

import MetaTrader5 as mt5
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    currency: str
    leverage: int
    name: str


def auto_connect(path: str = None) -> Optional[AccountInfo]:
    """
    Connect to MT5 terminal.
    If path is provided, connects to that specific terminal.
    Otherwise auto-detects the running terminal.
    Returns AccountInfo if successful, None otherwise.
    """
    kwargs = {}
    if path:
        kwargs['path'] = path
    if not mt5.initialize(**kwargs):
        log.error(f"MT5 initialize failed: {mt5.last_error()}")
        return None

    info = mt5.account_info()
    if not info:
        log.error(f"MT5 account_info failed: {mt5.last_error()}")
        mt5.shutdown()
        return None

    return AccountInfo(
        login=info.login,
        server=info.server,
        balance=info.balance,
        equity=info.equity,
        currency=info.currency,
        leverage=info.leverage,
        name=info.name,
    )


def disconnect():
    """Disconnect from MT5."""
    mt5.shutdown()


SYMBOL_ALIASES = {
    # Metals
    'XAUUSD': ['XAUUSD', 'GOLD', 'GOLD#', 'XAUUSD#', 'XAUUSD.cash', 'XAUUSDm', 'XAUUSD.a', 'XAUUSD.b', 'XAUUSD.c', 'GOLD.a'],
    'XAGUSD': ['XAGUSD', 'SILVER', 'SILVER#', 'XAGUSD#', 'XAGUSD.cash', 'XAGUSDm', 'XAGUSD.a'],
    # Forex majors
    'EURUSD': ['EURUSD', 'EURUSD#', 'EURUSDm', 'EURUSD.a', 'EURUSD.b', 'EURUSD.c'],
    'GBPUSD': ['GBPUSD', 'GBPUSD#', 'GBPUSDm', 'GBPUSD.a', 'GBPUSD.b', 'GBPUSD.c'],
    'USDJPY': ['USDJPY', 'USDJPY#', 'USDJPYm', 'USDJPY.a', 'USDJPY.b', 'USDJPY.c'],
    'GBPJPY': ['GBPJPY', 'GBPJPY#', 'GBPJPYm', 'GBPJPY.a', 'GBPJPY.b', 'GBPJPY.c'],
    'AUDUSD': ['AUDUSD', 'AUDUSD#', 'AUDUSDm', 'AUDUSD.a', 'AUDUSD.b'],
    'NZDUSD': ['NZDUSD', 'NZDUSD#', 'NZDUSDm', 'NZDUSD.a'],
    'USDCAD': ['USDCAD', 'USDCAD#', 'USDCADm', 'USDCAD.a'],
    'USDCHF': ['USDCHF', 'USDCHF#', 'USDCHFm', 'USDCHF.a'],
    # Forex cross
    'EURJPY': ['EURJPY', 'EURJPY#', 'EURJPYm', 'EURJPY.a'],
    'EURGBP': ['EURGBP', 'EURGBP#', 'EURGBPm', 'EURGBP.a'],
    'EURCHF': ['EURCHF', 'EURCHF#', 'EURCHFm', 'EURCHF.a'],
    'EURAUD': ['EURAUD', 'EURAUD#', 'EURAUDm', 'EURAUD.a'],
    'EURNZD': ['EURNZD', 'EURNZD#', 'EURNZDm', 'EURNZD.a'],
    'EURCAD': ['EURCAD', 'EURCAD#', 'EURCADm', 'EURCAD.a'],
    'AUDCAD': ['AUDCAD', 'AUDCAD#', 'AUDCADm', 'AUDCAD.a'],
    'AUDNZD': ['AUDNZD', 'AUDNZD#', 'AUDNZDm', 'AUDNZD.a'],
    'AUDJPY': ['AUDJPY', 'AUDJPY#', 'AUDJPYm', 'AUDJPY.a'],
    'AUDCHF': ['AUDCHF', 'AUDCHF#', 'AUDCHFm', 'AUDCHF.a'],
    'NZDJPY': ['NZDJPY', 'NZDJPY#', 'NZDJPYm', 'NZDJPY.a'],
    'NZDCHF': ['NZDCHF', 'NZDCHF#', 'NZDCHFm', 'NZDCHF.a'],
    'NZDCAD': ['NZDCAD', 'NZDCAD#', 'NZDCADm', 'NZDCAD.a'],
    'GBPAUD': ['GBPAUD', 'GBPAUD#', 'GBPAUDm', 'GBPAUD.a'],
    'GBPCAD': ['GBPCAD', 'GBPCAD#', 'GBPCADm', 'GBPCAD.a'],
    'GBPCHF': ['GBPCHF', 'GBPCHF#', 'GBPCHFm', 'GBPCHF.a'],
    'GBPNZD': ['GBPNZD', 'GBPNZD#', 'GBPNZDm', 'GBPNZD.a'],
    'CADCHF': ['CADCHF', 'CADCHF#', 'CADCHFm', 'CADCHF.a'],
    'CADJPY': ['CADJPY', 'CADJPY#', 'CADJPYm', 'CADJPY.a'],
    'CHFJPY': ['CHFJPY', 'CHFJPY#', 'CHFJPYm', 'CHFJPY.a'],
    # US Indices
    'NAS100': ['NAS100', 'US100', 'US100.cash', 'US100Cash#', 'USTEC', 'USTEC.cash', 'NAS100.cash', 'NAS100#', 'NDX100', 'USATECHIDXUSD', 'US100m'],
    'SP500': ['SP500', 'US500', 'US500.cash', 'US500Cash#', 'SPX500', 'SPX500.cash', 'SP500.cash', 'SP500#', 'USA500IDXUSD', 'US500m'],
    'US30': ['US30', 'US30.cash', 'US30Cash#', 'DJ30', 'DJ30.cash', 'US30#', 'USA30IDXUSD', 'US30m'],
    # EU Indices
    'GER40': ['GER40', 'GER40.cash', 'GER40Cash#', 'DAX40', 'DE40', 'DE40.cash', 'GER40#', 'DEUIDXEUR', 'GER40m'],
    'FRA40': ['FRA40', 'FRA40.cash', 'FRA40Cash#', 'FR40', 'FR40.cash', 'FRA40#', 'FRAIDXEUR', 'FRA40m'],
    'UK100': ['UK100', 'UK100.cash', 'UK100Cash#', 'FTSE100', 'UK100#', 'GBRIDXGBP', 'UK100m'],
    'EU50': ['EU50', 'EU50.cash', 'EU50Cash#', 'EUSTX50', 'STOXX50', 'EU50#', 'EUSIDXEUR'],
    'SWI20': ['SWI20', 'SWI20.cash', 'SWI20Cash#', 'SWI20#', 'CHEIDXCHF'],
    'ESP35': ['ESP35', 'ESP35.cash', 'ESP35Cash#', 'ESP35#', 'ESPIDXEUR'],
    'IT40': ['IT40', 'IT40.cash', 'IT40Cash#', 'IT40#', 'ITAIDXEUR'],
    # Asia Indices
    'JPN225': ['JPN225', 'JP225', 'JP225.cash', 'JP225Cash#', 'NI225', 'NIKKEI225', 'JPN225.cash', 'JPN225#', 'JPNIDXJPY', 'JP225m'],
    'HK50': ['HK50', 'HK50.cash', 'HK50Cash#', 'HSI50', 'HK50#', 'HKGIDXHKD', 'HK50m'],
    'AUS200': ['AUS200', 'AUS200.cash', 'AUS200Cash#', 'ASX200', 'AUS200#', 'AUSIDXAUD', 'AUS200m'],
    # Energy
    'WTIUSD': ['WTIUSD', 'USOIL', 'USOIL.cash', 'OILCash#', 'WTIUSD#', 'WTI', 'CL', 'CRUDEOIL', 'USOILm', 'USOIL#'],
    'BRENTUSD': ['BRENTUSD', 'UKOIL', 'UKOIL.cash', 'BRENT', 'BRN', 'UKOILm', 'UKOIL#'],
    'NATGAS': ['NATGAS', 'NATGAS#', 'NGAS', 'XNGUSD', 'NATGASm', 'NATGAS.cash'],
    # Crypto
    'BTCUSD': ['BTCUSD', 'BTCUSD#', 'BTC/USD', 'BTCUSDm', 'BITCOIN'],
    'ETHUSD': ['ETHUSD', 'ETHUSD#', 'ETH/USD', 'ETHUSDm', 'ETHEREUM'],
}


def get_symbol_info(symbol: str) -> Optional[dict]:
    """Get symbol info from MT5. Tries aliases and common broker suffixes."""
    # Build candidate list: aliases first, then generic suffixes
    candidates = []
    norm = symbol.upper().replace('#', '').replace('.CASH', '').replace('CASH', '')
    for key, aliases in SYMBOL_ALIASES.items():
        if norm in [a.upper().replace('#', '').replace('.CASH', '').replace('CASH', '') for a in [key] + aliases]:
            candidates.extend(aliases)
            break
    if not candidates:
        # Generic: try symbol as-is, then with common broker suffixes
        suffixes = ['', '#', '.cash', 'Cash#', '.cash#']
        candidates = [symbol + s for s in suffixes]
        # Also try without suffix if symbol already has one
        bare = symbol.replace('#', '').replace('.cash', '')
        if bare != symbol:
            candidates = [bare] + candidates

    for test_sym in candidates:
        info = mt5.symbol_info(test_sym)
        if info and info.visible:
            return {
                'name': test_sym,
                'point': info.point,
                'digits': info.digits,
                'trade_tick_size': info.trade_tick_size,
                'trade_tick_value': info.trade_tick_value,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
                'spread': info.spread,
            }
    return None


def calculate_lot_size(symbol_info: dict, risk_amount: float, sl_distance: float) -> float:
    """Calculate lot size based on risk amount and SL distance."""
    if sl_distance <= 0:
        return symbol_info['volume_min']

    tick_size = symbol_info['trade_tick_size']
    tick_value = symbol_info['trade_tick_value']

    if tick_size <= 0 or tick_value <= 0:
        return symbol_info['volume_min']

    sl_ticks = sl_distance / tick_size
    loss_per_lot = sl_ticks * tick_value
    lot = risk_amount / loss_per_lot if loss_per_lot > 0 else symbol_info['volume_min']

    # Round to volume_step
    step = symbol_info['volume_step']
    lot = round(lot / step) * step
    lot = max(lot, symbol_info['volume_min'])
    lot = min(lot, symbol_info['volume_max'])

    return round(lot, 2)


def place_order(symbol_name: str, direction: str, lot: float,
                sl: float, tp: float) -> dict:
    """Place a market order on MT5."""
    tick = mt5.symbol_info_tick(symbol_name)
    if not tick:
        return {'success': False, 'error': f'No tick data for {symbol_name}'}

    if direction == 'buy':
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol_name,
        'volume': lot,
        'type': order_type,
        'price': price,
        'sl': sl,
        'tp': tp,
        'deviation': 20,
        'magic': 12121,
        'comment': 'SignalCopier',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        return {'success': False, 'error': f'order_send returned None: {mt5.last_error()}'}

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {
            'success': True,
            'ticket': result.order,
            'price': result.price,
            'volume': result.volume,
        }
    else:
        return {
            'success': False,
            'error': f'retcode={result.retcode}, comment={result.comment}',
        }


def get_open_positions(magic: int = 12121) -> list:
    """Get all open positions placed by this bot."""
    positions = mt5.positions_get()
    if not positions:
        return []
    return [p for p in positions if p.magic == magic]


def get_account_equity() -> float:
    """Get current account equity."""
    info = mt5.account_info()
    return info.equity if info else 0.0
