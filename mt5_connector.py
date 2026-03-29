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


def get_symbol_info(symbol: str) -> Optional[dict]:
    """Get symbol info from MT5. Tries common broker suffixes."""
    suffixes = ['', '#', '.cash', 'Cash#']
    for suffix in suffixes:
        test_sym = symbol + suffix
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
