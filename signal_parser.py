"""
Parse ALL IASMC signal provider messages from Telegram.

Signal types:
1. OPEN:  "📈 SIGNAL: BUY XAUUSD" — Entry/SL/TP/Risk
2. CLOSE: "✅ RESULT: BUY XAUUSD -- Win (+1.40R)" — Trade closed
3. SL:    "🛡️ UPDATE: BUY XAUUSD -- SL Modified (Breakeven+)" — Move SL
4. PARTIAL:"🎯 UPDATE: SELL US30.cash -- Partial TP" — Close partial
5. PORTFOLIO:"💰 UPDATE: Portfolio Take Profit 💰" — Close all partially
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List

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
    raw_text: str = ''


@dataclass
class SignalClose:
    type: str = 'close'
    symbol: str = ''
    direction: str = ''
    result: str = ''
    r_multiple: float = 0.0
    pips: float = 0.0
    exit_reason: str = ''
    raw_text: str = ''


@dataclass
class SignalSLModified:
    type: str = 'sl_modified'
    symbol: str = ''
    direction: str = ''
    new_sl: float = 0.0
    old_sl: float = 0.0
    status: str = ''
    raw_text: str = ''


@dataclass
class SignalPartialTP:
    type: str = 'partial_tp'
    symbol: str = ''
    direction: str = ''
    closed_pct: float = 0.0
    close_price: float = 0.0
    remaining_pct: float = 0.0
    raw_text: str = ''


@dataclass
class SignalPortfolioTP:
    type: str = 'portfolio_tp'
    details: list = field(default_factory=list)
    total_locked_pct: float = 0.0
    floating_pct: float = 0.0
    raw_text: str = ''


def from_server_payload(data: dict):
    """Convert a signal server JSON payload into a typed Signal dataclass.

    The server stores signals with: source, signal_type, symbol, direction, payload (dict).
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


def detect_source(text: str) -> str:
    """Detect which bot sent the signal from [BotName] tag.

    TelegramSender prefixes all messages with <b>[BotName]</b> or [BotName].
    Returns bot name (e.g. 'IASMC', 'HybridSMC') or 'unknown'.
    """
    # HTML bold tag: <b>[BotName]</b> or plain [BotName]
    m = re.search(r'\[(\w+?)(?:_Signals?)?\]', text)
    if m:
        name = m.group(1)
        name_lower = name.lower()
        if 'iasmc' in name_lower:
            return 'IASMC'
        if 'hybrid' in name_lower:
            return 'HybridSMC'
        return name
    return 'unknown'


def parse_message(text: str):
    """Parse any signal provider message from Telegram.

    Supports both IASMC and HybridSMC formats (same structure).
    Returns typed dataclass or None.
    """
    if not text:
        return None
    if 'SIGNAL:' in text and 'Entry:' in text:
        return _parse_open(text)
    if 'RESULT:' in text:
        return _parse_close(text)
    if 'SL Modified' in text:
        return _parse_sl_modified(text)
    if 'Partial TP' in text:
        return _parse_partial_tp(text)
    if 'Portfolio Take Profit' in text:
        return _parse_portfolio_tp(text)
    return None


def _parse_open(text):
    try:
        sig = re.search(r'SIGNAL:\s*(BUY|SELL)\s+(\S+)', text, re.I)
        if not sig: return None
        entry = re.search(r'Entry:\s*([\d.]+)', text)
        sl = re.search(r'Stop Loss:\s*([\d.]+)', text)
        tp = re.search(r'Take Profit:\s*([\d.]+)', text)
        rr = re.search(r'Risk/Reward:\s*1:([\d.]+)', text)
        risk = re.search(r'Suggested Risk:\s*([\d.]+)%', text)
        if not all([entry, sl, tp]): return None
        if risk:
            suggested_risk = float(risk.group(1))
        else:
            suggested_risk = 1.0
            log.warning(f"No 'Suggested Risk' found in signal, defaulting to {suggested_risk}%")
        return SignalOpen(
            symbol=sig.group(2).strip(), direction=sig.group(1).lower(),
            entry=float(entry.group(1)), stop_loss=float(sl.group(1)),
            take_profit=float(tp.group(1)),
            risk_reward=float(rr.group(1)) if rr else 0.0,
            suggested_risk=suggested_risk,
            raw_text=text,
        )
    except (ValueError, AttributeError):
        return None


def _parse_close(text):
    try:
        m = re.search(r'RESULT:\s*(BUY|SELL)\s+(\S+)\s*--\s*(\w+)', text, re.I)
        if not m: return None
        r = re.search(r'([+-]?[\d.]+)R\)', text)
        pips = re.search(r'Pips:\s*([+-]?[\d.]+)', text)
        exit_r = re.search(r'Exit Reason:\s*(.+?)(?:\n|$)', text)
        result = m.group(3).lower()
        if result in ('win', 'tp'): result = 'win'
        elif result in ('loss', 'sl'): result = 'loss'
        else: result = 'breakeven'
        return SignalClose(
            symbol=m.group(2).strip(), direction=m.group(1).lower(), result=result,
            r_multiple=float(r.group(1)) if r else 0.0,
            pips=float(pips.group(1)) if pips else 0.0,
            exit_reason=exit_r.group(1).strip() if exit_r else '',
            raw_text=text,
        )
    except (ValueError, AttributeError):
        return None


def _parse_sl_modified(text):
    try:
        m = re.search(r'UPDATE:\s*(BUY|SELL)\s+(\S+)\s*--\s*SL Modified\s*\(([^)]+)\)', text, re.I)
        if not m: return None
        old = re.search(r'Old SL:\s*([\d.]+)', text)
        new = re.search(r'New SL:\s*([\d.]+)', text)
        return SignalSLModified(
            symbol=m.group(2).strip(), direction=m.group(1).lower(),
            new_sl=float(new.group(1)) if new else 0.0,
            old_sl=float(old.group(1)) if old else 0.0,
            status=m.group(3), raw_text=text,
        )
    except (ValueError, AttributeError):
        return None


def _parse_partial_tp(text):
    try:
        m = re.search(r'UPDATE:\s*(BUY|SELL)\s+(\S+)\s*--\s*Partial TP', text, re.I)
        if not m: return None
        closed = re.search(r'Closed\s+([\d.]+)%.*?at\s+([\d.]+)', text)
        remaining = re.search(r'Remaining:\s+([\d.]+)%', text)
        return SignalPartialTP(
            symbol=m.group(2).strip(), direction=m.group(1).lower(),
            closed_pct=float(closed.group(1)) if closed else 25.0,
            close_price=float(closed.group(2)) if closed else 0.0,
            remaining_pct=float(remaining.group(1)) if remaining else 75.0,
            raw_text=text,
        )
    except (ValueError, AttributeError):
        return None


def _parse_portfolio_tp(text):
    try:
        details = []
        for line in text.split('\n'):
            d = re.search(r'(\S+):\s*([\d.]+)/([\d.]+)\s*lots\s*\(([+-]?[\d.]+)%\)', line)
            if d:
                details.append((d.group(1), float(d.group(2)), float(d.group(3)), float(d.group(4))))
        locked = re.search(r'Total Locked:\s*([+-]?[\d.]+)%', text)
        floating = re.search(r'Remaining Float:\s*([+-]?[\d.]+)%', text)
        return SignalPortfolioTP(
            details=details,
            total_locked_pct=float(locked.group(1)) if locked else 0.0,
            floating_pct=float(floating.group(1)) if floating else 0.0,
            raw_text=text,
        )
    except (ValueError, AttributeError):
        return None
