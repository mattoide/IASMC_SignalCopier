"""
SignalCopier GUI — tkinter-based interface.
Auto-detects MT5, receives signals via Telegram Bot (zero config).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import json
import os

from mt5_connector import auto_connect, disconnect, get_open_positions, get_account_equity
from copier import SignalCopier

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'trading': {'use_signal_settings': True, 'custom_risk_pct': 1.0, 'max_positions': 5, 'max_per_symbol': 1}}


def save_config(config: dict):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class SignalCopierGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SignalCopier")
        self.root.geometry("600x550")
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
        self._update_equity()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='#e0e0e0', font=('Segoe UI', 10))
        style.configure('Title.TLabel', background='#1a1a2e', foreground='#00ff88', font=('Segoe UI', 16, 'bold'))
        style.configure('Status.TLabel', background='#1a1a2e', foreground='#ffaa00', font=('Segoe UI', 10, 'bold'))
        style.configure('TLabelframe', background='#1a1a2e', foreground='#e0e0e0')
        style.configure('TLabelframe.Label', background='#1a1a2e', foreground='#e0e0e0', font=('Segoe UI', 10, 'bold'))
        style.configure('TCheckbutton', background='#1a1a2e', foreground='#e0e0e0')

        # Title
        ttk.Label(self.root, text="SIGNAL COPIER", style='Title.TLabel').pack(pady=(10, 5))

        # MT5 Status Frame
        mt5_frame = ttk.LabelFrame(self.root, text="MetaTrader 5", padding=10)
        mt5_frame.pack(fill='x', padx=10, pady=5)

        info_grid = ttk.Frame(mt5_frame)
        info_grid.pack(fill='x')

        self.mt5_status = ttk.Label(info_grid, text="  Searching...", style='Status.TLabel')
        self.mt5_status.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 5))

        ttk.Label(info_grid, text="Account:").grid(row=1, column=0, sticky='w')
        self.mt5_account = ttk.Label(info_grid, text="—")
        self.mt5_account.grid(row=1, column=1, sticky='w', padx=(5, 20))

        ttk.Label(info_grid, text="Server:").grid(row=1, column=2, sticky='w')
        self.mt5_server = ttk.Label(info_grid, text="—")
        self.mt5_server.grid(row=1, column=3, sticky='w', padx=(5, 0))

        ttk.Label(info_grid, text="Balance:").grid(row=2, column=0, sticky='w')
        self.mt5_balance = ttk.Label(info_grid, text="—")
        self.mt5_balance.grid(row=2, column=1, sticky='w', padx=(5, 20))

        ttk.Label(info_grid, text="Equity:").grid(row=2, column=2, sticky='w')
        self.mt5_equity = ttk.Label(info_grid, text="—")
        self.mt5_equity.grid(row=2, column=3, sticky='w', padx=(5, 0))

        ttk.Label(info_grid, text="Positions:").grid(row=3, column=0, sticky='w')
        self.mt5_positions = ttk.Label(info_grid, text="—")
        self.mt5_positions.grid(row=3, column=1, sticky='w', padx=(5, 20))

        ttk.Button(mt5_frame, text="Reconnect", command=self._try_connect_mt5).pack(anchor='e', pady=(5, 0))

        # Settings Frame
        settings_frame = ttk.LabelFrame(self.root, text="Trading Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)

        self.use_signal_var = tk.BooleanVar(value=self.config['trading'].get('use_signal_settings', True))
        ttk.Checkbutton(
            settings_frame, text="Use signal's suggested risk (ignore custom settings below)",
            variable=self.use_signal_var, command=self._toggle_custom
        ).pack(anchor='w')

        self.custom_frame = ttk.Frame(settings_frame)
        self.custom_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(self.custom_frame, text="Risk %:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.risk_var = tk.DoubleVar(value=self.config['trading'].get('custom_risk_pct', 1.0))
        self.risk_entry = ttk.Entry(self.custom_frame, textvariable=self.risk_var, width=8)
        self.risk_entry.grid(row=0, column=1, sticky='w')

        ttk.Label(self.custom_frame, text="Max positions:").grid(row=0, column=2, sticky='w', padx=(20, 5))
        self.maxpos_var = tk.IntVar(value=self.config['trading'].get('max_positions', 5))
        ttk.Entry(self.custom_frame, textvariable=self.maxpos_var, width=5).grid(row=0, column=3, sticky='w')

        ttk.Label(self.custom_frame, text="Max per symbol:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=(3, 0))
        self.maxsym_var = tk.IntVar(value=self.config['trading'].get('max_per_symbol', 1))
        ttk.Entry(self.custom_frame, textvariable=self.maxsym_var, width=5).grid(row=1, column=1, sticky='w', pady=(3, 0))

        self._toggle_custom()

        # Control Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill='x', padx=10, pady=5)

        self.start_btn = ttk.Button(btn_frame, text="  START  ", command=self._start_copier)
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="  STOP  ", command=self._stop_copier, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        self.copier_status = ttk.Label(btn_frame, text="STOPPED", style='Status.TLabel')
        self.copier_status.pack(side='right', padx=5)

        # Log
        log_frame = ttk.LabelFrame(self.root, text="Signal Log", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, bg='#0d1117', fg='#c9d1d9',
            font=('Consolas', 9), insertbackground='white', wrap='word'
        )
        self.log_text.pack(fill='both', expand=True)

    def _toggle_custom(self):
        state = 'disabled' if self.use_signal_var.get() else 'normal'
        for child in self.custom_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass

    def _try_connect_mt5(self):
        self.account_info = auto_connect()
        if self.account_info:
            self.connected = True
            self.mt5_status.configure(text="  Connected", foreground='#00ff88')
            self.mt5_account.configure(text=str(self.account_info.login))
            self.mt5_server.configure(text=self.account_info.server)
            self.mt5_balance.configure(text=f"{self.account_info.balance:.2f} {self.account_info.currency}")
            self.mt5_equity.configure(text=f"{self.account_info.equity:.2f} {self.account_info.currency}")
            self.mt5_positions.configure(text=str(len(get_open_positions())))
            self._add_log(f"MT5 connected: {self.account_info.login} @ {self.account_info.server}")
        else:
            self.connected = False
            self.mt5_status.configure(text="  Not found — open MT5 and login first", foreground='#ff4444')
            self._add_log("Please open MetaTrader 5 and login to your account, then click Reconnect.")

    def _update_equity(self):
        if self.connected:
            try:
                equity = get_account_equity()
                positions = get_open_positions()
                if equity > 0:
                    self.mt5_equity.configure(text=f"{equity:.2f}")
                    self.mt5_positions.configure(text=str(len(positions)))
            except Exception:
                pass
        self.root.after(5000, self._update_equity)

    def _add_log(self, msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S') if 'datetime' in dir() else ''
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{timestamp}] {msg}\n")
        self.log_text.see('end')

    def _start_copier(self):
        if not self.connected:
            messagebox.showerror("Error", "MT5 not connected.\n\nPlease open MetaTrader 5, login to your account, then click Reconnect.")
            return

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
        self.copier_status.configure(text="STARTING...", foreground='#ffaa00')

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
        self._add_log(f"TRADE EXECUTED: {trade['direction'].upper()} {trade['symbol']} "
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
