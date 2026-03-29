"""
Parse IASMC signal provider messages from Telegram.

Expected format:
    📈 SIGNAL: BUY XAUUSD

    Entry: 4450.50
    Stop Loss: 4440.00 (-105.0 pips)
    Take Profit: 4465.00 (+145.0 pips)
    Risk/Reward: 1:1.4
    Suggested Risk: 0.5%

    27 Mar 2026 14:30 UTC
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedSignal:
    symbol: str
    direction: str  # 'buy' or 'sell'
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    suggested_risk: float
    raw_text: str


def parse_signal(text: str) -> Optional[ParsedSignal]:
    """Parse an IASMC signal message. Returns None if not a valid signal."""
    if 'SIGNAL:' not in text:
        return None

    try:
        # Direction + Symbol: "📈 SIGNAL: BUY XAUUSD" or "📉 SIGNAL: SELL GBPUSD"
        sig_match = re.search(r'SIGNAL:\s*(BUY|SELL)\s+(\S+)', text, re.IGNORECASE)
        if not sig_match:
            return None
        direction = sig_match.group(1).lower()
        symbol = sig_match.group(2).strip()

        # Entry price
        entry_match = re.search(r'Entry:\s*([\d.]+)', text)
        if not entry_match:
            return None
        entry = float(entry_match.group(1))

        # Stop Loss
        sl_match = re.search(r'Stop Loss:\s*([\d.]+)', text)
        if not sl_match:
            return None
        stop_loss = float(sl_match.group(1))

        # Take Profit
        tp_match = re.search(r'Take Profit:\s*([\d.]+)', text)
        if not tp_match:
            return None
        take_profit = float(tp_match.group(1))

        # Risk/Reward (optional)
        rr_match = re.search(r'Risk/Reward:\s*1:([\d.]+)', text)
        risk_reward = float(rr_match.group(1)) if rr_match else 0.0

        # Suggested Risk (optional)
        risk_match = re.search(r'Suggested Risk:\s*([\d.]+)%', text)
        suggested_risk = float(risk_match.group(1)) if risk_match else 1.0

        return ParsedSignal(
            symbol=symbol,
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            suggested_risk=suggested_risk,
            raw_text=text,
        )

    except (ValueError, AttributeError):
        return None


def parse_close_signal(text: str) -> Optional[dict]:
    """Parse a trade closed message. Returns dict with symbol, side, result."""
    if 'CLOSED' not in text.upper() and 'RESULT' not in text.upper():
        return None

    try:
        # "✅ RESULT: BUY XAUUSD" or "TRADE CLOSED"
        match = re.search(r'(?:RESULT|CLOSED).*?(BUY|SELL)\s+(\S+)', text, re.IGNORECASE)
        if not match:
            return None

        pnl_match = re.search(r'P&?L:\s*([+-]?[\d.]+)', text)
        pips_match = re.search(r'([+-]?[\d.]+)\s*pips', text, re.IGNORECASE)

        return {
            'direction': match.group(1).lower(),
            'symbol': match.group(2).strip(),
            'pnl': float(pnl_match.group(1)) if pnl_match else None,
            'pips': float(pips_match.group(1)) if pips_match else None,
        }
    except (ValueError, AttributeError):
        return None
