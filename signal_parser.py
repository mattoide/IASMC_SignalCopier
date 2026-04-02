"""
Parse signal server JSON payloads into typed dataclasses.

Signal types:
1. OPEN:       Entry/SL/TP/Risk
2. CLOSE:      Trade closed (info only)
3. SL_MODIFIED: SL moved
4. PARTIAL_TP:  Partial position close
5. PORTFOLIO_TP: Portfolio-level partial close
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class SignalOpen:
    type: str = 'open'
    symbol: str = ''
    direction: str = ''
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    suggested_risk: float = 1.0


@dataclass
class SignalClose:
    type: str = 'close'
    symbol: str = ''
    direction: str = ''
    result: str = ''
    r_multiple: float = 0.0
    pips: float = 0.0
    exit_reason: str = ''


@dataclass
class SignalSLModified:
    type: str = 'sl_modified'
    symbol: str = ''
    direction: str = ''
    new_sl: float = 0.0
    old_sl: float = 0.0
    status: str = ''


@dataclass
class SignalPartialTP:
    type: str = 'partial_tp'
    symbol: str = ''
    direction: str = ''
    closed_pct: float = 0.0
    close_price: float = 0.0
    remaining_pct: float = 0.0


@dataclass
class SignalPortfolioTP:
    type: str = 'portfolio_tp'
    details: list = field(default_factory=list)
    total_locked_pct: float = 0.0
    floating_pct: float = 0.0


def from_server_payload(data: dict):
    """Convert a signal server JSON payload into a typed Signal dataclass.

    The server stores signals with: source, signal_type, symbol, direction, payload (dict).
    Returns (signal, source) tuple.
    """
    sig_type = data.get('signal_type', '')
    payload = data.get('payload', {})
    source = data.get('source', 'unknown')

    if sig_type == 'open':
        return SignalOpen(
            symbol=payload.get('symbol', ''),
            direction=payload.get('direction', ''),
            entry=float(payload.get('entry', 0)),
            stop_loss=float(payload.get('stop_loss', 0)),
            take_profit=float(payload.get('take_profit', 0)),
            suggested_risk=float(payload.get('suggested_risk', 1.0)),
        ), source
    elif sig_type == 'close':
        result = payload.get('result', '').lower()
        if result in ('win', 'tp'):
            result = 'win'
        elif result in ('loss', 'sl'):
            result = 'loss'
        else:
            result = 'breakeven'
        return SignalClose(
            symbol=payload.get('symbol', ''),
            direction=payload.get('direction', ''),
            result=result,
            r_multiple=float(payload.get('r_multiple', 0)),
            pips=float(payload.get('pips', 0)),
            exit_reason=payload.get('exit_reason', ''),
        ), source
    elif sig_type == 'sl_modified':
        return SignalSLModified(
            symbol=payload.get('symbol', ''),
            direction=payload.get('direction', ''),
            old_sl=float(payload.get('old_sl', 0)),
            new_sl=float(payload.get('new_sl', 0)),
            status=payload.get('status', ''),
        ), source
    elif sig_type == 'partial_tp':
        return SignalPartialTP(
            symbol=payload.get('symbol', ''),
            direction=payload.get('direction', ''),
            closed_pct=float(payload.get('closed_pct', 25)),
            close_price=float(payload.get('close_price', 0)),
        ), source
    elif sig_type == 'portfolio_tp':
        details = []
        for d in payload.get('details', []):
            details.append((
                d.get('symbol', ''),
                float(d.get('partial_vol', 0)),
                float(d.get('total_vol', 0)),
                float(d.get('pnl_pct', 0)),
            ))
        return SignalPortfolioTP(
            details=details,
            total_locked_pct=float(payload.get('total_locked_pct', 0)),
            floating_pct=float(payload.get('floating_pct', 0)),
        ), source

    return None, source
