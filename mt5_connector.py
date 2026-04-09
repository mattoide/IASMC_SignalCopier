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
    'XAUUSD': ['XAUUSD', 'GOLD', 'GOLD#', 'XAUUSD#', 'XAUUSD.cash', 'XAUUSDm', 'XAUUSD.a', 'XAUUSD.b', 'XAUUSD.c', 'GOLD.a', 'XAUUSD.r', 'XAUUSD.fn'],
    'XAGUSD': ['XAGUSD', 'SILVER', 'SILVER#', 'XAGUSD#', 'XAGUSD.cash', 'XAGUSDm', 'XAGUSD.a', 'XAGUSD.r', 'XAGUSD.fn'],
    # Forex majors
    'EURUSD': ['EURUSD', 'EURUSD#', 'EURUSDm', 'EURUSD.a', 'EURUSD.b', 'EURUSD.c', 'EURUSD.r', 'EURUSD.fn'],
    'GBPUSD': ['GBPUSD', 'GBPUSD#', 'GBPUSDm', 'GBPUSD.a', 'GBPUSD.b', 'GBPUSD.c', 'GBPUSD.r', 'GBPUSD.fn'],
    'USDJPY': ['USDJPY', 'USDJPY#', 'USDJPYm', 'USDJPY.a', 'USDJPY.b', 'USDJPY.c', 'USDJPY.r', 'USDJPY.fn'],
    'GBPJPY': ['GBPJPY', 'GBPJPY#', 'GBPJPYm', 'GBPJPY.a', 'GBPJPY.b', 'GBPJPY.c', 'GBPJPY.r', 'GBPJPY.fn'],
    'AUDUSD': ['AUDUSD', 'AUDUSD#', 'AUDUSDm', 'AUDUSD.a', 'AUDUSD.b', 'AUDUSD.r', 'AUDUSD.fn'],
    'NZDUSD': ['NZDUSD', 'NZDUSD#', 'NZDUSDm', 'NZDUSD.a', 'NZDUSD.r', 'NZDUSD.fn'],
    'USDCAD': ['USDCAD', 'USDCAD#', 'USDCADm', 'USDCAD.a', 'USDCAD.r', 'USDCAD.fn'],
    'USDCHF': ['USDCHF', 'USDCHF#', 'USDCHFm', 'USDCHF.a', 'USDCHF.r', 'USDCHF.fn'],
    # Forex cross
    'EURJPY': ['EURJPY', 'EURJPY#', 'EURJPYm', 'EURJPY.a', 'EURJPY.r', 'EURJPY.fn'],
    'EURGBP': ['EURGBP', 'EURGBP#', 'EURGBPm', 'EURGBP.a', 'EURGBP.r', 'EURGBP.fn'],
    'EURCHF': ['EURCHF', 'EURCHF#', 'EURCHFm', 'EURCHF.a', 'EURCHF.r', 'EURCHF.fn'],
    'EURAUD': ['EURAUD', 'EURAUD#', 'EURAUDm', 'EURAUD.a', 'EURAUD.r', 'EURAUD.fn'],
    'EURNZD': ['EURNZD', 'EURNZD#', 'EURNZDm', 'EURNZD.a', 'EURNZD.r', 'EURNZD.fn'],
    'EURCAD': ['EURCAD', 'EURCAD#', 'EURCADm', 'EURCAD.a', 'EURCAD.r', 'EURCAD.fn'],
    'AUDCAD': ['AUDCAD', 'AUDCAD#', 'AUDCADm', 'AUDCAD.a', 'AUDCAD.r', 'AUDCAD.fn'],
    'AUDNZD': ['AUDNZD', 'AUDNZD#', 'AUDNZDm', 'AUDNZD.a', 'AUDNZD.r', 'AUDNZD.fn'],
    'AUDJPY': ['AUDJPY', 'AUDJPY#', 'AUDJPYm', 'AUDJPY.a', 'AUDJPY.r', 'AUDJPY.fn'],
    'AUDCHF': ['AUDCHF', 'AUDCHF#', 'AUDCHFm', 'AUDCHF.a', 'AUDCHF.r', 'AUDCHF.fn'],
    'NZDJPY': ['NZDJPY', 'NZDJPY#', 'NZDJPYm', 'NZDJPY.a', 'NZDJPY.r', 'NZDJPY.fn'],
    'NZDCHF': ['NZDCHF', 'NZDCHF#', 'NZDCHFm', 'NZDCHF.a', 'NZDCHF.r', 'NZDCHF.fn'],
    'NZDCAD': ['NZDCAD', 'NZDCAD#', 'NZDCADm', 'NZDCAD.a', 'NZDCAD.r', 'NZDCAD.fn'],
    'GBPAUD': ['GBPAUD', 'GBPAUD#', 'GBPAUDm', 'GBPAUD.a', 'GBPAUD.r', 'GBPAUD.fn'],
    'GBPCAD': ['GBPCAD', 'GBPCAD#', 'GBPCADm', 'GBPCAD.a', 'GBPCAD.r', 'GBPCAD.fn'],
    'GBPCHF': ['GBPCHF', 'GBPCHF#', 'GBPCHFm', 'GBPCHF.a', 'GBPCHF.r', 'GBPCHF.fn'],
    'GBPNZD': ['GBPNZD', 'GBPNZD#', 'GBPNZDm', 'GBPNZD.a', 'GBPNZD.r', 'GBPNZD.fn'],
    'CADCHF': ['CADCHF', 'CADCHF#', 'CADCHFm', 'CADCHF.a', 'CADCHF.r', 'CADCHF.fn'],
    'CADJPY': ['CADJPY', 'CADJPY#', 'CADJPYm', 'CADJPY.a', 'CADJPY.r', 'CADJPY.fn'],
    'CHFJPY': ['CHFJPY', 'CHFJPY#', 'CHFJPYm', 'CHFJPY.a', 'CHFJPY.r', 'CHFJPY.fn'],
    # US Indices
    'NAS100': ['NAS100', 'US100', 'US100.cash', 'US100Cash#', 'USTEC', 'USTEC.cash', 'NAS100.cash', 'NAS100#', 'NDX100', 'USATECHIDXUSD', 'US100m', 'NAS100.r', 'NAS100.fn', 'US100.r', 'US100.fn', 'USTEC.r', 'USTEC.fn'],
    'SP500': ['SP500', 'US500', 'US500.cash', 'US500Cash#', 'SPX500', 'SPX500.cash', 'SP500.cash', 'SP500#', 'USA500IDXUSD', 'US500m', 'SP500.r', 'SP500.fn', 'US500.r', 'US500.fn', 'SPX500.r', 'SPX500.fn'],
    'US30': ['US30', 'US30.cash', 'US30Cash#', 'DJ30', 'DJ30.cash', 'US30#', 'USA30IDXUSD', 'US30m', 'US30.r', 'US30.fn', 'DJ30.r', 'DJ30.fn'],
    # EU Indices
    'GER40': ['GER40', 'GER30', 'GER40.cash', 'GER40Cash#', 'DAX40', 'DE40', 'DE40.cash', 'GER40#', 'DEUIDXEUR', 'GER40m', 'GER40.r', 'GER40.fn', 'DE40.r', 'DE40.fn'],
    'FRA40': ['FRA40', 'FRA40.cash', 'FRA40Cash#', 'FR40', 'FR40.cash', 'FRA40#', 'FRAIDXEUR', 'FRA40m', 'FRA40.r', 'FRA40.fn'],
    'UK100': ['UK100', 'UK100.cash', 'UK100Cash#', 'FTSE100', 'UK100#', 'GBRIDXGBP', 'UK100m', 'UK100.r', 'UK100.fn'],
    'EU50': ['EU50', 'EU50.cash', 'EU50Cash#', 'EUSTX50', 'STOXX50', 'EU50#', 'EUSIDXEUR', 'EU50.r', 'EU50.fn'],
    'SWI20': ['SWI20', 'SWI20.cash', 'SWI20Cash#', 'SWI20#', 'CHEIDXCHF', 'SWI20.r', 'SWI20.fn'],
    'ESP35': ['ESP35', 'ESP35.cash', 'ESP35Cash#', 'ESP35#', 'ESPIDXEUR', 'ESP35.r', 'ESP35.fn'],
    'IT40': ['IT40', 'IT40.cash', 'IT40Cash#', 'IT40#', 'ITAIDXEUR', 'IT40.r', 'IT40.fn'],
    # Asia Indices
    'JPN225': ['JPN225', 'JP225', 'JP225.cash', 'JP225Cash#', 'NI225', 'NIKKEI225', 'JPN225.cash', 'JPN225#', 'JPNIDXJPY', 'JP225m', 'JPN225.r', 'JPN225.fn', 'JP225.r', 'JP225.fn'],
    'HK50': ['HK50', 'HK50.cash', 'HK50Cash#', 'HSI50', 'HK50#', 'HKGIDXHKD', 'HK50m', 'HK50.r', 'HK50.fn'],
    'AUS200': ['AUS200', 'AUS200.cash', 'AUS200Cash#', 'ASX200', 'AUS200#', 'AUSIDXAUD', 'AUS200m', 'AUS200.r', 'AUS200.fn'],
    # Energy
    'WTIUSD': ['WTIUSD', 'USOIL', 'USOUSD', 'USOIL.cash', 'OILCash#', 'WTIUSD#', 'WTI', 'CL', 'CRUDEOIL', 'USOILm', 'USOIL#', 'WTIUSD.r', 'WTIUSD.fn', 'USOIL.r', 'USOIL.fn'],
    'BRENTUSD': ['BRENTUSD', 'UKOIL', 'UKOUSD', 'UKOIL.cash', 'BRENT', 'BRN', 'UKOILm', 'UKOIL#', 'BRENTUSD.r', 'BRENTUSD.fn', 'UKOIL.r', 'UKOIL.fn'],
    'NATGAS': ['NATGAS', 'NATGAS#', 'NGAS', 'XNGUSD', 'NATGASm', 'NATGAS.cash', 'NATGAS.r', 'NATGAS.fn', 'XNGUSD.r', 'XNGUSD.fn'],
    # Crypto
    'BTCUSD': ['BTCUSD', 'BTCUSD#', 'BTC/USD', 'BTCUSDm', 'BITCOIN', 'BTCUSD.r', 'BTCUSD.fn'],
    'ETHUSD': ['ETHUSD', 'ETHUSD#', 'ETH/USD', 'ETHUSDm', 'ETHEREUM', 'ETHUSD.r', 'ETHUSD.fn'],
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
        suffixes = ['', '#', '.cash', 'Cash#', '.cash#', '.r', '.fn', '.raw', '.e']
        candidates = [symbol + s for s in suffixes]
        # Also try without suffix if symbol already has one
        bare = symbol.replace('#', '').replace('.cash', '')
        if bare != symbol:
            candidates = [bare] + candidates

    # First pass: find a tradable symbol (trade_mode == FULL)
    for test_sym in candidates:
        info = mt5.symbol_info(test_sym)
        if info is None:
            continue
        # Skip symbols that are not tradable (e.g. USDJPY exists on XM but only USDJPY# is tradable)
        if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            continue
        # Enable symbol in MarketWatch if not visible
        if not info.visible:
            mt5.symbol_select(test_sym, True)
            info = mt5.symbol_info(test_sym)
        if info:
            return {
                'name': test_sym,
                'point': info.point,
                'digits': info.digits,
                'trade_tick_size': info.trade_tick_size,
                'trade_tick_value': info.trade_tick_value,
                'trade_contract_size': info.trade_contract_size,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
                'spread': info.spread,
            }

    # Second pass: fallback to any existing symbol (in case trade_mode check is too strict)
    for test_sym in candidates:
        info = mt5.symbol_info(test_sym)
        if info is None:
            continue
        if not info.visible:
            mt5.symbol_select(test_sym, True)
            info = mt5.symbol_info(test_sym)
        if info:
            return {
                'name': test_sym,
                'point': info.point,
                'digits': info.digits,
                'trade_tick_size': info.trade_tick_size,
                'trade_tick_value': info.trade_tick_value,
                'trade_contract_size': info.trade_contract_size,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
                'spread': info.spread,
            }
    return None


def calculate_lot_size(symbol_info: dict, risk_amount: float, sl_distance: float,
                       entry_price: float = 0, direction: str = 'buy') -> float:
    """Calculate lot size based on risk amount and SL distance.

    Primary method: mt5.order_calc_profit() — lets MT5 handle contract size,
    currency conversion, and tick value correctly for ALL symbol types.
    Fallback: tick-based calculation if order_calc_profit fails.
    """
    sym = symbol_info['name']

    if sl_distance <= 0:
        log.warning(f"LOT_CALC {sym}: sl_distance={sl_distance} <= 0, returning volume_min")
        return symbol_info['volume_min']

    # --- Primary method: order_calc_profit ---
    # Simulate 1 lot losing sl_distance to get loss in account currency
    if entry_price > 0:
        if direction == 'buy':
            price_open = entry_price
            price_close = entry_price - sl_distance
        else:
            price_open = entry_price
            price_close = entry_price + sl_distance

        action = mt5.ORDER_TYPE_BUY if direction == 'buy' else mt5.ORDER_TYPE_SELL
        profit_1lot = mt5.order_calc_profit(action, sym, 1.0, price_open, price_close)

        if profit_1lot is not None and profit_1lot < 0:
            loss_per_lot = abs(profit_1lot)
            raw_lot = risk_amount / loss_per_lot

            log.info(f"LOT_CALC {sym} [order_calc_profit]: {direction} entry={entry_price} "
                     f"sl_dist={sl_distance} loss_1lot={loss_per_lot:.4f} "
                     f"risk={risk_amount:.2f} raw_lot={raw_lot:.4f}")

            step = symbol_info['volume_step']
            lot = round(raw_lot / step) * step
            lot = max(lot, symbol_info['volume_min'])
            lot = min(lot, symbol_info['volume_max'])
            log.info(f"LOT_CALC {sym}: final_lot={round(lot, 2)}")
            return round(lot, 2)
        else:
            log.warning(f"LOT_CALC {sym}: order_calc_profit returned {profit_1lot}, falling back to tick method")

    # --- Fallback: tick-based calculation ---
    tick_size = symbol_info['trade_tick_size']
    tick_value = symbol_info['trade_tick_value']

    if tick_size <= 0 or tick_value <= 0:
        log.warning(f"LOT_CALC {sym}: tick_size={tick_size} tick_value={tick_value} invalid, returning volume_min")
        return symbol_info['volume_min']

    sl_ticks = sl_distance / tick_size
    loss_per_lot = sl_ticks * tick_value
    raw_lot = risk_amount / loss_per_lot if loss_per_lot > 0 else symbol_info['volume_min']

    log.info(f"LOT_CALC {sym} [tick_fallback]: sl_dist={sl_distance} tick_size={tick_size} "
             f"tick_value={tick_value} contract_size={symbol_info.get('trade_contract_size', '?')} "
             f"sl_ticks={sl_ticks:.1f} loss_per_lot={loss_per_lot:.4f} "
             f"risk={risk_amount:.2f} raw_lot={raw_lot:.4f}")

    step = symbol_info['volume_step']
    lot = round(raw_lot / step) * step
    lot = max(lot, symbol_info['volume_min'])
    lot = min(lot, symbol_info['volume_max'])

    log.info(f"LOT_CALC {sym}: final_lot={round(lot, 2)}")
    return round(lot, 2)


def _get_filling_mode(symbol_name: str):
    """Detect the filling mode supported by the broker for this symbol."""
    info = mt5.symbol_info(symbol_name)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    fm = info.filling_mode
    if fm & 1:
        return mt5.ORDER_FILLING_FOK
    if fm & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def place_order(symbol_name: str, direction: str, lot: float,
                sl: float, tp: float, magic: int = 12121,
                comment: str = 'SignalCopier') -> dict:
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
        'magic': magic,
        'comment': comment,
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': _get_filling_mode(symbol_name),
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


def find_position_by_symbol(symbol: str, direction: str = None, magic: int = 12121) -> Optional[object]:
    """Find an open position by symbol (tries aliases). Returns MT5 position object."""
    positions = get_open_positions(magic)
    sym_info = get_symbol_info(symbol)
    mt5_name = sym_info['name'] if sym_info else symbol

    for p in positions:
        if p.symbol == mt5_name:
            if direction is None:
                return p
            pos_dir = 'buy' if p.type == 0 else 'sell'
            if pos_dir == direction.lower():
                return p
    return None


def modify_sl(ticket: int, new_sl: float) -> dict:
    """Modify SL of an open position."""
    pos = None
    positions = mt5.positions_get(ticket=ticket)
    if positions:
        pos = positions[0]
    if not pos:
        return {'success': False, 'error': f'Position {ticket} not found'}

    request = {
        'action': mt5.TRADE_ACTION_SLTP,
        'position': ticket,
        'symbol': pos.symbol,
        'sl': new_sl,
        'tp': pos.tp,
        'magic': pos.magic,
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return {'success': True}
    return {'success': False, 'error': f'retcode={result.retcode if result else "None"}, comment={result.comment if result else ""}'}


def close_partial(ticket: int, volume_to_close: float) -> dict:
    """Close partial volume of a position."""
    pos = None
    positions = mt5.positions_get(ticket=ticket)
    if positions:
        pos = positions[0]
    if not pos:
        return {'success': False, 'error': f'Position {ticket} not found'}

    # Determine close direction
    if pos.type == 0:  # BUY -> close with SELL
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(pos.symbol).bid
    else:  # SELL -> close with BUY
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).ask

    # Round volume to step
    info = mt5.symbol_info(pos.symbol)
    step = info.volume_step if info else 0.01
    volume_to_close = round(volume_to_close / step) * step
    volume_to_close = max(volume_to_close, info.volume_min if info else 0.01)
    volume_to_close = min(volume_to_close, pos.volume)

    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'position': ticket,
        'symbol': pos.symbol,
        'volume': round(volume_to_close, 2),
        'type': order_type,
        'price': price,
        'deviation': 20,
        'magic': pos.magic,
        'comment': 'SignalCopier partial',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': _get_filling_mode(pos.symbol),
    }
    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return {'success': True, 'volume_closed': volume_to_close}
    return {'success': False, 'error': f'retcode={result.retcode if result else "None"}'}


def close_position(ticket: int) -> dict:
    """Close a full position."""
    pos = None
    positions = mt5.positions_get(ticket=ticket)
    if positions:
        pos = positions[0]
    if not pos:
        return {'success': False, 'error': f'Position {ticket} not found'}
    return close_partial(ticket, pos.volume)


def get_account_equity() -> float:
    """Get current account equity."""
    info = mt5.account_info()
    return info.equity if info else 0.0
