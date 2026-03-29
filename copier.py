"""
Core copier logic — listens to Telegram channel and executes trades on MT5.
"""

import asyncio
import logging
import json
import os
from datetime import datetime, timezone

from telethon import TelegramClient, events

from signal_parser import parse_signal, parse_close_signal
from mt5_connector import (
    get_symbol_info, calculate_lot_size, place_order,
    get_open_positions, get_account_equity,
)

log = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


class SignalCopier:
    """Listens to Telegram signals and copies them to MT5."""

    def __init__(self, config: dict, on_log=None, on_trade=None, on_status=None):
        self.config = config
        self.on_log = on_log or (lambda msg: None)
        self.on_trade = on_trade or (lambda trade: None)
        self.on_status = on_status or (lambda status: None)
        self.running = False
        self.client = None
        self.trades_today = 0
        self.pnl_today = 0.0

    @property
    def use_signal_settings(self) -> bool:
        return self.config.get('trading', {}).get('use_signal_settings', True)

    @property
    def custom_risk_pct(self) -> float:
        return self.config.get('trading', {}).get('custom_risk_pct', 1.0)

    @property
    def max_positions(self) -> int:
        return self.config.get('trading', {}).get('max_positions', 5)

    @property
    def max_per_symbol(self) -> int:
        return self.config.get('trading', {}).get('max_per_symbol', 1)

    def _log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        full = f"[{timestamp}] {msg}"
        log.info(msg)
        self.on_log(full)

    async def start(self):
        """Start listening for signals."""
        tg = self.config.get('telegram', {})
        api_id = tg.get('api_id')
        api_hash = tg.get('api_hash')
        channel = tg.get('channel', '')

        if not api_id or not api_hash:
            self._log("ERROR: Telegram API credentials not configured")
            return

        session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session')
        self.client = TelegramClient(session_path, api_id, api_hash)

        await self.client.start()
        self._log("Connected to Telegram")

        # Resolve channel
        try:
            entity = await self.client.get_entity(channel)
            self._log(f"Listening to channel: {channel}")
        except Exception as e:
            self._log(f"ERROR: Cannot find channel {channel}: {e}")
            return

        self.running = True
        self.on_status('running')

        @self.client.on(events.NewMessage(chats=[entity]))
        async def handle_message(event):
            if not self.running:
                return
            await self._process_message(event.message.text or '')

        self._log("Signal copier started. Waiting for signals...")

        try:
            await self.client.run_until_disconnected()
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            self.on_status('stopped')

    async def stop(self):
        """Stop the copier."""
        self.running = False
        if self.client:
            await self.client.disconnect()
        self._log("Signal copier stopped")

    async def _process_message(self, text: str):
        """Process an incoming Telegram message."""
        signal = parse_signal(text)
        if not signal:
            # Check for close signal
            close = parse_close_signal(text)
            if close:
                self._log(f"Trade closed: {close['direction'].upper()} {close['symbol']} "
                          f"PnL: {close.get('pnl', '?')}")
            return

        self._log(f"SIGNAL: {signal.direction.upper()} {signal.symbol} "
                  f"@ {signal.entry} SL={signal.stop_loss} TP={signal.take_profit}")

        # Check max positions
        open_pos = get_open_positions()
        if len(open_pos) >= self.max_positions:
            self._log(f"SKIP: Max positions reached ({len(open_pos)}/{self.max_positions})")
            return

        # Check per-symbol limit
        sym_count = sum(1 for p in open_pos if signal.symbol in p.symbol)
        if sym_count >= self.max_per_symbol:
            self._log(f"SKIP: Max per symbol {signal.symbol} ({sym_count}/{self.max_per_symbol})")
            return

        # Find symbol on MT5
        sym_info = get_symbol_info(signal.symbol)
        if not sym_info:
            self._log(f"SKIP: Symbol {signal.symbol} not found on MT5")
            return

        # Calculate lot size
        if self.use_signal_settings:
            risk_pct = signal.suggested_risk
        else:
            risk_pct = self.custom_risk_pct

        equity = get_account_equity()
        risk_amount = equity * (risk_pct / 100)
        sl_distance = abs(signal.entry - signal.stop_loss)
        lot = calculate_lot_size(sym_info, risk_amount, sl_distance)

        self._log(f"Placing order: {signal.direction.upper()} {sym_info['name']} "
                  f"lot={lot} risk={risk_pct}% (${risk_amount:.2f})")

        # Place order
        result = place_order(
            sym_info['name'], signal.direction, lot,
            signal.stop_loss, signal.take_profit,
        )

        if result['success']:
            self._log(f"ORDER FILLED: ticket={result['ticket']} @ {result['price']} lot={result['volume']}")
            self.trades_today += 1
            self.on_trade({
                'symbol': signal.symbol,
                'direction': signal.direction,
                'entry': result['price'],
                'lot': result['volume'],
                'sl': signal.stop_loss,
                'tp': signal.take_profit,
                'ticket': result['ticket'],
                'time': datetime.now(timezone.utc).isoformat(),
            })
        else:
            self._log(f"ORDER FAILED: {result['error']}")
