"""
Core copier logic — Bot Telegram reads channel messages, executes trades on MT5.
Handles: OPEN, CLOSE (info only), SL MODIFY, PARTIAL TP, PORTFOLIO TP.
"""

import asyncio
import logging
import json
import os
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from signal_parser import (
    parse_message, SignalOpen, SignalClose, SignalSLModified,
    SignalPartialTP, SignalPortfolioTP,
)
from mt5_connector import (
    get_symbol_info, calculate_lot_size, place_order,
    get_open_positions, get_account_equity,
    find_position_by_symbol, modify_sl, close_partial,
)

log = logging.getLogger(__name__)

import base64 as _b
BOT_TOKEN = _b.b64decode("ODczNTE5Mjg2NjpBQUVSQ3pyWFFIMzQyNzRGQ1p1MXRKSHRJMIZZX2ZCUDFB").decode()


class SignalCopier:
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
        if not self.running:
            return
        msg = update.channel_post or update.message
        if not msg or not msg.text:
            return
        await self._process_message(msg.text)

    async def _process_message(self, text: str):
        signal = parse_message(text)
        if signal is None:
            return

        if isinstance(signal, SignalOpen):
            await self._handle_open(signal)
        elif isinstance(signal, SignalClose):
            self._handle_close(signal)
        elif isinstance(signal, SignalSLModified):
            self._handle_sl_modified(signal)
        elif isinstance(signal, SignalPartialTP):
            self._handle_partial_tp(signal)
        elif isinstance(signal, SignalPortfolioTP):
            self._handle_portfolio_tp(signal)

    # ── OPEN ──────────────────────────────────────────────────
    async def _handle_open(self, sig: SignalOpen):
        self._log(f"SIGNAL: {sig.direction.upper()} {sig.symbol} "
                  f"@ {sig.entry} SL={sig.stop_loss} TP={sig.take_profit}")

        open_pos = get_open_positions()
        if len(open_pos) >= self.max_positions:
            self._log(f"SKIP: Max positions ({len(open_pos)}/{self.max_positions})")
            return

        sym_count = sum(1 for p in open_pos if sig.symbol in p.symbol)
        if sym_count >= self.max_per_symbol:
            self._log(f"SKIP: Max per symbol {sig.symbol} ({sym_count}/{self.max_per_symbol})")
            return

        sym_info = get_symbol_info(sig.symbol)
        if not sym_info:
            self._log(f"SKIP: Symbol {sig.symbol} not found on MT5")
            return

        risk_pct = sig.suggested_risk if self.use_signal_settings else self.custom_risk_pct
        equity = get_account_equity()
        risk_amount = equity * (risk_pct / 100)
        sl_distance = abs(sig.entry - sig.stop_loss)
        lot = calculate_lot_size(sym_info, risk_amount, sl_distance)

        self._log(f"Placing: {sig.direction.upper()} {sym_info['name']} "
                  f"lot={lot} risk={risk_pct}% (${risk_amount:.2f})")

        result = place_order(sym_info['name'], sig.direction, lot, sig.stop_loss, sig.take_profit)

        if result['success']:
            self._log(f"FILLED: ticket={result['ticket']} @ {result['price']} lot={result['volume']}")
            self.trades_today += 1
            self.on_trade({
                'type': 'open', 'symbol': sig.symbol, 'direction': sig.direction,
                'entry': result['price'], 'lot': result['volume'],
                'sl': sig.stop_loss, 'tp': sig.take_profit, 'ticket': result['ticket'],
            })
        else:
            self._log(f"FAILED: {result['error']}")

    # ── CLOSE (info only — position closed by SL/TP on broker side) ──
    def _handle_close(self, sig: SignalClose):
        icon = "+" if sig.result == 'win' else "-" if sig.result == 'loss' else "~"
        self._log(f"CLOSED: {sig.direction.upper()} {sig.symbol} "
                  f"{icon}{sig.r_multiple:.2f}R ({sig.pips:+.1f} pips) — {sig.exit_reason}")

    # ── SL MODIFIED ───────────────────────────────────────────
    def _handle_sl_modified(self, sig: SignalSLModified):
        self._log(f"SL UPDATE: {sig.direction.upper()} {sig.symbol} "
                  f"SL {sig.old_sl} -> {sig.new_sl} ({sig.status})")

        pos = find_position_by_symbol(sig.symbol, sig.direction)
        if not pos:
            self._log(f"  No matching position found for {sig.symbol} {sig.direction}")
            return

        result = modify_sl(pos.ticket, sig.new_sl)
        if result['success']:
            self._log(f"  SL modified: ticket={pos.ticket} new_sl={sig.new_sl}")
        else:
            self._log(f"  SL modify failed: {result['error']}")

    # ── PARTIAL TP ────────────────────────────────────────────
    def _handle_partial_tp(self, sig: SignalPartialTP):
        self._log(f"PARTIAL TP: {sig.direction.upper()} {sig.symbol} "
                  f"close {sig.closed_pct:.0f}% @ {sig.close_price}")

        pos = find_position_by_symbol(sig.symbol, sig.direction)
        if not pos:
            self._log(f"  No matching position found for {sig.symbol} {sig.direction}")
            return

        vol_to_close = pos.volume * (sig.closed_pct / 100)
        result = close_partial(pos.ticket, vol_to_close)
        if result['success']:
            self._log(f"  Closed {result['volume_closed']:.2f} lots of {pos.volume:.2f}")
        else:
            self._log(f"  Partial close failed: {result['error']}")

    # ── PORTFOLIO TP ──────────────────────────────────────────
    def _handle_portfolio_tp(self, sig: SignalPortfolioTP):
        self._log(f"PORTFOLIO TP: locked {sig.total_locked_pct:+.2f}%, "
                  f"float {sig.floating_pct:+.2f}%")

        positions = get_open_positions()
        if not positions:
            self._log("  No positions to close")
            return

        # Close proportional amount from each position
        for pos in positions:
            # Find matching detail from signal
            matched = None
            for sym, pv, vol, pnl in (sig.details or []):
                if sym in pos.symbol or pos.symbol in sym:
                    matched = (pv, vol)
                    break

            if matched:
                vol_to_close = matched[0]  # Use the exact partial volume from signal
            else:
                # Default: close 50% if no detail match
                vol_to_close = pos.volume * 0.5

            result = close_partial(pos.ticket, vol_to_close)
            if result['success']:
                self._log(f"  {pos.symbol}: closed {result['volume_closed']:.2f} lots")
            else:
                self._log(f"  {pos.symbol}: close failed — {result['error']}")

    # ── START/STOP ────────────────────────────────────────────
    async def start(self):
        self.running = True
        self.on_status('running')
        self._log("Starting Telegram bot...")

        self.app = Application.builder().token(BOT_TOKEN).build()
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self._handle_message
        ))

        self._log("Bot connected. Listening for signals...")

        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)
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
        self._log("Stopping...")
        self.running = False
