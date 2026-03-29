"""
SignalCopier GUI — tkinter-based interface.
Auto-detects MT5, shows account info, configurable settings, live log.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import json
import os
import sys

from mt5_connector import auto_connect, disconnect, get_open_positions, get_account_equity
from copier import SignalCopier

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'telegram': {'api_id': 0, 'api_hash': '', 'channel': ''},
        'trading': {'use_signal_settings': True, 'custom_risk_pct': 1.0, 'max_positions': 5, 'max_per_symbol': 1}
    }


def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class SignalCopierGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SignalCopier")
        self.root.geometry("700x600")
        self.root.configure(bg='#1a1a2e')
        self.root.resizable(True, True)

        self.config = load_config()
        self.copier = None
        self.copier_thread = None
        self.loop = None
        self.account_info = None
        self.connected = False

        self._build_ui()
        self._try_connect_mt5()

        # Update equity periodically
        self._update_equity()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='#e0e0e0', font=('Consolas', 10))
        style.configure('Title.TLabel', background='#1a1a2e', foreground='#00ff88', font=('Consolas', 14, 'bold'))
        style.configure('Status.TLabel', background='#1a1a2e', foreground='#ffaa00', font=('Consolas', 10))
        style.configure('TButton', font=('Consolas', 10))
        style.configure('Green.TButton', foreground='#00ff88')
        style.configure('Red.TButton', foreground='#ff4444')

        # Title
        ttk.Label(self.root, text="SIGNAL COPIER", style='Title.TLabel').pack(pady=(10, 5))

        # MT5 Status Frame
        mt5_frame = ttk.LabelFrame(self.root, text="MT5 Connection", padding=10)
        mt5_frame.pack(fill='x', padx=10, pady=5)

        self.mt5_status = ttk.Label(mt5_frame, text="Disconnected", style='Status.TLabel')
        self.mt5_status.pack(anchor='w')

        self.mt5_account = ttk.Label(mt5_frame, text="Account: —")
        self.mt5_account.pack(anchor='w')

        self.mt5_balance = ttk.Label(mt5_frame, text="Balance: —")
        self.mt5_balance.pack(anchor='w')

        self.mt5_equity = ttk.Label(mt5_frame, text="Equity: —")
        self.mt5_equity.pack(anchor='w')

        self.mt5_positions = ttk.Label(mt5_frame, text="Positions: —")
        self.mt5_positions.pack(anchor='w')

        ttk.Button(mt5_frame, text="Reconnect MT5", command=self._try_connect_mt5).pack(anchor='e', pady=(5, 0))

        # Settings Frame
        settings_frame = ttk.LabelFrame(self.root, text="Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)

        # Use signal settings checkbox
        self.use_signal_var = tk.BooleanVar(value=self.config['trading'].get('use_signal_settings', True))
        self.use_signal_cb = ttk.Checkbutton(
            settings_frame, text="Use signal's suggested settings (risk, SL, TP)",
            variable=self.use_signal_var, command=self._toggle_custom_settings
        )
        self.use_signal_cb.pack(anchor='w')

        # Custom settings (shown when checkbox is off)
        self.custom_frame = ttk.Frame(settings_frame)
        self.custom_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(self.custom_frame, text="Risk %:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.risk_var = tk.DoubleVar(value=self.config['trading'].get('custom_risk_pct', 1.0))
        self.risk_entry = ttk.Entry(self.custom_frame, textvariable=self.risk_var, width=8)
        self.risk_entry.grid(row=0, column=1, sticky='w')

        ttk.Label(self.custom_frame, text="Max positions:").grid(row=0, column=2, sticky='w', padx=(15, 5))
        self.maxpos_var = tk.IntVar(value=self.config['trading'].get('max_positions', 5))
        ttk.Entry(self.custom_frame, textvariable=self.maxpos_var, width=5).grid(row=0, column=3, sticky='w')

        ttk.Label(self.custom_frame, text="Max per symbol:").grid(row=1, column=0, sticky='w', padx=(0, 5))
        self.maxsym_var = tk.IntVar(value=self.config['trading'].get('max_per_symbol', 1))
        ttk.Entry(self.custom_frame, textvariable=self.maxsym_var, width=5).grid(row=1, column=1, sticky='w')

        self._toggle_custom_settings()

        # Control Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill='x', padx=10, pady=5)

        self.start_btn = ttk.Button(btn_frame, text="START", command=self._start_copier)
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="STOP", command=self._stop_copier, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        self.copier_status = ttk.Label(btn_frame, text="STOPPED", style='Status.TLabel')
        self.copier_status.pack(side='right', padx=5)

        # Log
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, bg='#0d1117', fg='#c9d1d9',
            font=('Consolas', 9), insertbackground='white'
        )
        self.log_text.pack(fill='both', expand=True)

    def _toggle_custom_settings(self):
        if self.use_signal_var.get():
            for child in self.custom_frame.winfo_children():
                child.configure(state='disabled')
        else:
            for child in self.custom_frame.winfo_children():
                child.configure(state='normal')

    def _try_connect_mt5(self):
        self.account_info = auto_connect()
        if self.account_info:
            self.connected = True
            self.mt5_status.configure(text="Connected", foreground='#00ff88')
            self.mt5_account.configure(text=f"Account: {self.account_info.login} ({self.account_info.server})")
            self.mt5_balance.configure(text=f"Balance: {self.account_info.balance:.2f} {self.account_info.currency}")
            self.mt5_equity.configure(text=f"Equity: {self.account_info.equity:.2f} {self.account_info.currency}")
            self.mt5_positions.configure(text=f"Positions: {len(get_open_positions())}")
            self._add_log(f"MT5 connected: {self.account_info.login} @ {self.account_info.server}")
        else:
            self.connected = False
            self.mt5_status.configure(text="Disconnected — open MT5 and login first", foreground='#ff4444')
            self._add_log("MT5 not found. Please open MetaTrader 5 and login to your account.")

    def _update_equity(self):
        if self.connected:
            try:
                equity = get_account_equity()
                positions = get_open_positions()
                if equity > 0:
                    self.mt5_equity.configure(text=f"Equity: {equity:.2f}")
                    self.mt5_positions.configure(text=f"Positions: {len(positions)}")
            except Exception:
                pass
        self.root.after(5000, self._update_equity)

    def _add_log(self, msg: str):
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')

    def _start_copier(self):
        if not self.connected:
            messagebox.showerror("Error", "MT5 not connected. Open MetaTrader 5 and login first.")
            return

        # Save settings
        self.config['trading'] = {
            'use_signal_settings': self.use_signal_var.get(),
            'custom_risk_pct': self.risk_var.get(),
            'max_positions': self.maxpos_var.get(),
            'max_per_symbol': self.maxsym_var.get(),
        }
        save_config(self.config)

        self.copier = SignalCopier(
            config=self.config,
            on_log=lambda msg: self.root.after(0, self._add_log, msg),
            on_trade=lambda t: self.root.after(0, self._on_trade, t),
            on_status=lambda s: self.root.after(0, self._on_status, s),
        )

        self.loop = asyncio.new_event_loop()
        self.copier_thread = threading.Thread(target=self._run_copier, daemon=True)
        self.copier_thread.start()

        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.copier_status.configure(text="RUNNING", foreground='#00ff88')

    def _run_copier(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.copier.start())

    def _stop_copier(self):
        if self.copier and self.loop:
            asyncio.run_coroutine_threadsafe(self.copier.stop(), self.loop)
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.copier_status.configure(text="STOPPED", foreground='#ffaa00')

    def _on_trade(self, trade: dict):
        self._add_log(f"TRADE: {trade['direction'].upper()} {trade['symbol']} "
                      f"lot={trade['lot']} @ {trade['entry']}")

    def _on_status(self, status: str):
        if status == 'running':
            self.copier_status.configure(text="RUNNING", foreground='#00ff88')
        else:
            self.copier_status.configure(text="STOPPED", foreground='#ffaa00')
            self.start_btn.configure(state='normal')
            self.stop_btn.configure(state='disabled')

    def run(self):
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.copier:
            self._stop_copier()
        disconnect()
        self.root.destroy()


def main():
    app = SignalCopierGUI()
    app.run()


if __name__ == '__main__':
    main()
