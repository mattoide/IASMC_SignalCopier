"""
Core copier logic — Polls signal server, executes trades on MT5.
Handles: OPEN, CLOSE (info only), SL MODIFY, PARTIAL TP, PORTFOLIO TP.
Tracks which bot opened each position for correct update routing.
"""

import asyncio
import logging
import json
import os
import socket
import requests
from datetime import datetime, timezone
from urllib3.util.connection import allowed_gai_family  # noqa: F401

# --- DNS fallback via Google DNS-over-HTTPS (bypasses VPN DNS issues) ---
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}
_resolving_doh = False


def _resolve_doh(hostname):
    """Resolve hostname via Google DoH at IP 8.8.8.8 (no DNS needed for the request itself)."""
    cached = _dns_cache.get(hostname)
    if cached:
        return cached
    try:
        import urllib.request
        import json as _json
        # Use IP 8.8.8.8 directly to avoid recursive DNS resolution
        url = f'https://8.8.8.8/resolve?name={hostname}&type=A'
        req = urllib.request.Request(url, headers={'Accept': 'application/dns-json'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            for ans in data.get('Answer', []):
                if ans.get('type') == 1:
                    _dns_cache[hostname] = ans['data']
                    return ans['data']
    except Exception:
        pass
    return None


def _patched_getaddrinfo(host, port, *args, **kwargs):
    global _resolving_doh
    # Avoid recursion: if we're already resolving via DoH, use original resolver
    if _resolving_doh:
        return _orig_getaddrinfo(host, port, *args, **kwargs)
    try:
        return _orig_getaddrinfo(host, port, *args, **kwargs)
    except socket.gaierror:
        _resolving_doh = True
        try:
            ip = _resolve_doh(host)
        finally:
            _resolving_doh = False
        if ip:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port if port else 443))]
        raise


socket.getaddrinfo = _patched_getaddrinfo

from signal_parser import (
    from_server_payload,
    SignalOpen, SignalClose, SignalSLModified,
    SignalPartialTP, SignalPortfolioTP,
)
from mt5_connector import (
    get_symbol_info, calculate_lot_size, place_order,
    get_open_positions, get_account_equity,
    find_position_by_symbol, modify_sl, close_partial,
)

log = logging.getLogger(__name__)

# Magic numbers per source bot (different from live bots to avoid conflicts)
BOT_MAGIC = {
    'IASMC': 12121,
    'HybridSMC': 12122,
}
DEFAULT_MAGIC = 12121

# Persistent state file for position tracking
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'positions_state.json')


class SignalCopier:
    def __init__(self, config: dict, on_log=None, on_trade=None, on_status=None):
        self.config = config
        self.on_log = on_log or (lambda msg: None)
        self.on_trade = on_trade or (lambda trade: None)
        self.on_status = on_status or (lambda status: None)
        self.running = False
        self.trades_today = 0
        # ticket -> {'source': 'IASMC', 'symbol': 'XAUUSD', 'direction': 'buy'}
        self._position_map, self._last_signal_id = self._load_state()

    @property
    def enabled_bots(self) -> list:
        return self.config.get('enabled_bots', ['IASMC', 'HybridSMC'])

    @property
    def use_signal_settings(self) -> bool:
        return self.config.get('trading', {}).get('use_signal_settings', True)

    @property
    def custom_risk_pct(self) -> float:
        return self.config.get('trading', {}).get('custom_risk_pct', 1.0)

    @property
    def max_positions(self) -> int:
        return self.config.get('trading', {}).get('max_positions', 0)

    @property
    def max_per_symbol(self) -> int:
        return self.config.get('trading', {}).get('max_per_symbol', 1)

    def _load_state(self) -> tuple:
        """Load position tracking state and last_signal_id from disk."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                last_id = data.pop('_last_signal_id', 0)
                positions = {int(k): v for k, v in data.items()}
                return positions, last_id
            except Exception:
                pass
        return {}, 0

    def _save_state(self):
        """Persist position tracking state and last_signal_id."""
        try:
            save_data = dict(self._position_map)
            save_data['_last_signal_id'] = self._last_signal_id
            with open(STATE_FILE, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            log.warning(f"Failed to save state: {e}")

    def _recover_positions_from_mt5(self):
        """Recover open positions from MT5 that belong to the copier but aren't tracked.

        On restart, positions_state.json may be lost/empty. This rebuilds _position_map
        from MT5 open positions matching copier magic numbers, so SL updates and partial
        closes continue to work.
        """
        magic_to_source = {v: k for k, v in BOT_MAGIC.items()}
        recovered = 0
        for magic, source in magic_to_source.items():
            for pos in get_open_positions(magic):
                if pos.ticket not in self._position_map:
                    direction = 'buy' if pos.type == 0 else 'sell'
                    # Extract source from comment if available (e.g. "SC_IASMC")
                    src = source
                    if pos.comment and pos.comment.startswith('SC_'):
                        src = pos.comment[3:]
                    self._position_map[pos.ticket] = {
                        'source': src,
                        'symbol': pos.symbol,
                        'direction': direction,
                        'entry': pos.price_open,
                    }
                    recovered += 1
        if recovered:
            self._save_state()
            self._log(f"Recovered {recovered} open position(s) from MT5")

    def _cleanup_closed_positions(self):
        """Remove entries for positions that no longer exist on MT5."""
        if not self._position_map:
            return
        open_tickets = set()
        for magic in BOT_MAGIC.values():
            for p in get_open_positions(magic):
                open_tickets.add(p.ticket)
        closed = [t for t in self._position_map if t not in open_tickets]
        if closed:
            for t in closed:
                del self._position_map[t]
            self._save_state()

    def _log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        full = f"[{timestamp}] {msg}"
        log.info(msg)
        self.on_log(full)

    def _get_magic(self, source: str) -> int:
        return BOT_MAGIC.get(source, DEFAULT_MAGIC)

    # -- OPEN ---------------------------------------------------------------
    async def _handle_open(self, sig: SignalOpen, source: str):
        src_tag = f"[{source}] " if source != 'unknown' else ""
        self._log(f"{src_tag}SIGNAL: {sig.direction.upper()} {sig.symbol} "
                  f"@ {sig.entry} SL={sig.stop_loss} TP={sig.take_profit}")

        magic = self._get_magic(source)
        total_pos = sum(len(get_open_positions(m)) for m in BOT_MAGIC.values())

        if self.max_positions > 0 and total_pos >= self.max_positions:
            self._log(f"SKIP: Max positions ({total_pos}/{self.max_positions})")
            return

        # Count per-symbol across all bots
        all_pos = []
        for m in BOT_MAGIC.values():
            all_pos.extend(get_open_positions(m))
        sym_count = sum(1 for p in all_pos if sig.symbol in p.symbol)
        if sym_count >= self.max_per_symbol:
            self._log(f"SKIP: Max per symbol {sig.symbol} ({sym_count}/{self.max_per_symbol})")
            return

        sym_info = get_symbol_info(sig.symbol)
        if not sym_info:
            self._log(f"SKIP: Symbol {sig.symbol} not found on MT5")
            return

        if self.use_signal_settings:
            risk_pct = sig.suggested_risk
            risk_mode = f"signal ({risk_pct}%)"
        else:
            risk_pct = self.custom_risk_pct
            risk_mode = f"custom ({risk_pct}%)"

        self._log(f"{src_tag}Risk mode: {risk_mode} | signal_suggested={sig.suggested_risk}%")

        equity = get_account_equity()
        risk_amount = equity * (risk_pct / 100)
        sl_distance = abs(sig.entry - sig.stop_loss)
        lot = calculate_lot_size(sym_info, risk_amount, sl_distance,
                                 entry_price=sig.entry, direction=sig.direction)

        self._log(f"{src_tag}Placing: {sig.direction.upper()} {sym_info['name']} "
                  f"lot={lot} risk={risk_pct}% equity={equity:.2f} risk_amount={risk_amount:.2f}")

        result = place_order(sym_info['name'], sig.direction, lot, sig.stop_loss, sig.take_profit, magic=magic, comment=f'SC_{source}')

        if result['success']:
            ticket = result['ticket']
            self._log(f"{src_tag}FILLED: ticket={ticket} @ {result['price']} lot={result['volume']}")
            self.trades_today += 1

            self._position_map[ticket] = {
                'source': source,
                'symbol': sig.symbol,
                'direction': sig.direction,
                'entry': result['price'],
            }
            self._save_state()

            self.on_trade({
                'type': 'open', 'symbol': sig.symbol, 'direction': sig.direction,
                'entry': result['price'], 'lot': result['volume'],
                'sl': sig.stop_loss, 'tp': sig.take_profit, 'ticket': ticket,
                'source': source,
            })
        else:
            self._log(f"{src_tag}FAILED: {result['error']}")

    # -- CLOSE (info only) --------------------------------------------------
    def _handle_close(self, sig: SignalClose, source: str):
        src_tag = f"[{source}] " if source != 'unknown' else ""
        icon = "+" if sig.result == 'win' else "-" if sig.result == 'loss' else "~"
        self._log(f"{src_tag}CLOSED: {sig.direction.upper()} {sig.symbol} "
                  f"{icon}{sig.r_multiple:.2f}R ({sig.pips:+.1f} pips) -- {sig.exit_reason}")
        self._cleanup_closed_positions()

    # -- SL MODIFIED --------------------------------------------------------
    def _handle_sl_modified(self, sig: SignalSLModified, source: str):
        src_tag = f"[{source}] " if source != 'unknown' else ""
        self._log(f"{src_tag}SL UPDATE: {sig.direction.upper()} {sig.symbol} "
                  f"SL {sig.old_sl} -> {sig.new_sl} ({sig.status})")

        magic = self._get_magic(source)
        pos = find_position_by_symbol(sig.symbol, sig.direction, magic)
        if not pos:
            if source == 'unknown':
                for m in BOT_MAGIC.values():
                    pos = find_position_by_symbol(sig.symbol, sig.direction, m)
                    if pos:
                        break
            if not pos:
                self._log(f"  No matching position found for {sig.symbol} {sig.direction} (source={source})")
                return

        result = modify_sl(pos.ticket, sig.new_sl)
        if result['success']:
            self._log(f"  SL modified: ticket={pos.ticket} new_sl={sig.new_sl}")
        else:
            self._log(f"  SL modify failed: {result['error']}")

    # -- PARTIAL TP ---------------------------------------------------------
    def _handle_partial_tp(self, sig: SignalPartialTP, source: str):
        src_tag = f"[{source}] " if source != 'unknown' else ""
        self._log(f"{src_tag}PARTIAL TP: {sig.direction.upper()} {sig.symbol} "
                  f"close {sig.closed_pct:.0f}% @ {sig.close_price}")

        magic = self._get_magic(source)
        pos = find_position_by_symbol(sig.symbol, sig.direction, magic)
        if not pos:
            if source == 'unknown':
                for m in BOT_MAGIC.values():
                    pos = find_position_by_symbol(sig.symbol, sig.direction, m)
                    if pos:
                        break
            if not pos:
                self._log(f"  No matching position found for {sig.symbol} {sig.direction} (source={source})")
                return

        vol_to_close = pos.volume * (sig.closed_pct / 100)
        result = close_partial(pos.ticket, vol_to_close)
        if result['success']:
            self._log(f"  Closed {result['volume_closed']:.2f} lots of {pos.volume:.2f}")
        else:
            self._log(f"  Partial close failed: {result['error']}")

    # -- PORTFOLIO TP -------------------------------------------------------
    def _handle_portfolio_tp(self, sig: SignalPortfolioTP, source: str):
        src_tag = f"[{source}] " if source != 'unknown' else ""
        self._log(f"{src_tag}PORTFOLIO TP: locked {sig.total_locked_pct:+.2f}%, "
                  f"float {sig.floating_pct:+.2f}%")

        magic = self._get_magic(source)
        positions = get_open_positions(magic)
        if not positions:
            self._log("  No positions to close")
            return

        for pos in positions:
            matched = None
            for sym, pv, vol, pnl in (sig.details or []):
                if sym in pos.symbol or pos.symbol in sym:
                    matched = (pv, vol)
                    break

            if matched:
                vol_to_close = matched[0]
            else:
                vol_to_close = pos.volume * 0.5

            result = close_partial(pos.ticket, vol_to_close)
            if result['success']:
                self._log(f"  {pos.symbol}: closed {result['volume_closed']:.2f} lots")
            else:
                self._log(f"  {pos.symbol}: close failed -- {result['error']}")

    # -- SERVER POLLING -----------------------------------------------------
    async def _poll_server(self):
        """Poll signal server for new signals."""
        server_url = self.config.get('server', {}).get('url', '').rstrip('/')
        poll_interval = self.config.get('server', {}).get('poll_interval', 5)
        sources = ','.join(self.enabled_bots) if self.enabled_bots else ''
        last_id = self._last_signal_id

        # Get latest server id to skip old signals (only if no saved state)
        if last_id == 0:
            try:
                resp = requests.get(
                    f"{server_url}/api/signals/latest",
                    params={'after_id': 0, 'source': sources},
                    timeout=10,
                )
                if resp.status_code == 200:
                    signals = resp.json().get('signals', [])
                    if signals:
                        last_id = max(s['id'] for s in signals)
                        self._log(f"First run: skipping {len(signals)} existing signals (last_id={last_id})")
            except Exception as e:
                self._log(f"Server initial sync failed: {e}")
        else:
            self._log(f"Resuming from last signal #{last_id}")

        self._log(f"Polling server every {poll_interval}s...")

        while self.running:
            try:
                resp = requests.get(
                    f"{server_url}/api/signals/latest",
                    params={'after_id': last_id, 'source': sources},
                    timeout=10,
                )
                if resp.status_code == 200:
                    signals = resp.json().get('signals', [])
                    for sig_data in signals:
                        sig_id = sig_data['id']
                        if sig_id > last_id:
                            last_id = sig_id
                            self._last_signal_id = last_id
                            self._save_state()
                        signal, source = from_server_payload(sig_data)
                        if signal is None:
                            continue
                        if source not in self.enabled_bots:
                            continue

                        self._log(f"New signal #{sig_id}: {sig_data.get('signal_type')} "
                                  f"{sig_data.get('symbol', '')} from {source}")

                        if isinstance(signal, SignalOpen):
                            await self._handle_open(signal, source)
                        elif isinstance(signal, SignalClose):
                            self._handle_close(signal, source)
                        elif isinstance(signal, SignalSLModified):
                            self._handle_sl_modified(signal, source)
                        elif isinstance(signal, SignalPartialTP):
                            self._handle_partial_tp(signal, source)
                        elif isinstance(signal, SignalPortfolioTP):
                            self._handle_portfolio_tp(signal, source)
                elif resp.status_code != 200:
                    self._log(f"Server returned {resp.status_code}")

            except requests.ConnectionError:
                self._log("Server unreachable, retrying...")
            except Exception as e:
                self._log(f"Server poll error: {e}")

            try:
                await asyncio.sleep(poll_interval)
            except Exception:
                pass

    # -- START/STOP ---------------------------------------------------------
    async def start(self):
        self.running = True
        self.on_status('running')
        bots_str = ', '.join(self.enabled_bots) if self.enabled_bots else 'ALL'
        self._recover_positions_from_mt5()
        self._cleanup_closed_positions()

        self._log(f"Connecting to signal server... (sources: {bots_str})")
        try:
            await self._poll_server()
        except BaseException as e:
            self._log(f"ERROR: {type(e).__name__}: {e}")
        finally:
            self.running = False
            self.on_status('stopped')

    async def stop(self):
        self._log("Stopping...")
        self.running = False
