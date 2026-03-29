"""
Core copier logic — Bot Telegram reads channel messages, executes trades on MT5.
Zero user config needed for Telegram — bot token embedded.
"""

import asyncio
import logging
import json
import os
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from signal_parser import parse_signal, parse_close_signal
from mt5_connector import (
    get_symbol_info, calculate_lot_size, place_order,
    get_open_positions, get_account_equity,
)

log = logging.getLogger(__name__)

# Bot token — read-only bot, can only receive messages from the channel
BOT_TOKEN = "8735192866:AAERCzrXQH34274FCZu1tJJtI2ZYj_fBP1A"


class SignalCopier:
    """Listens to Telegram channel via Bot and copies trades to MT5."""

    def __init__(self, config: dict, on_log=None, on_trade=None, on_status=None):
        self.config = config
        self.on_log = on_log or (lambda msg: None)
        self.on_trade = on_trade or (lambda trade: None)
        self.on_status = on_status or (lambda status: None)
        self.running = False
        self.app = None
        self.trades_today = 0

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

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming channel message."""
        if not self.running:
            return

        # Get message text (channel posts come as channel_post, not message)
        msg = update.channel_post or update.message
        if not msg or not msg.text:
            return

        text = msg.text
        await self._process_signal(text)

    async def _process_signal(self, text: str):
        """Process a signal message."""
        signal = parse_signal(text)
        if not signal:
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

        self._log(f"Placing: {signal.direction.upper()} {sym_info['name']} "
                  f"lot={lot} risk={risk_pct}% (${risk_amount:.2f})")

        # Place order
        result = place_order(
            sym_info['name'], signal.direction, lot,
            signal.stop_loss, signal.take_profit,
        )

        if result['success']:
            self._log(f"FILLED: ticket={result['ticket']} @ {result['price']} lot={result['volume']}")
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
            self._log(f"FAILED: {result['error']}")

    async def start(self):
        """Start the bot."""
        self.running = True
        self.on_status('running')
        self._log("Starting Telegram bot...")

        self.app = Application.builder().token(BOT_TOKEN).build()

        # Handle all text messages (from channels and groups)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_message
        ))

        self._log("Bot connected. Listening for signals...")

        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            self._log(f"ERROR: {e}")
        finally:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception:
                pass
            self.running = False
            self.on_status('stopped')

    async def stop(self):
        """Stop the bot."""
        self._log("Stopping...")
        self.running = False
