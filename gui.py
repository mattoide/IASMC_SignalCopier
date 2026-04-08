"""
SignalCopier GUI — tkinter-based interface with EN/IT language support.
Auto-detects MT5, receives signals from signal server via polling.
Supports selecting which bots to copy signals from (IASMC, HybridSMC).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import asyncio
import json
import os
import sys
from datetime import datetime

from mt5_connector import auto_connect, disconnect, get_open_positions, get_account_equity
from copier import SignalCopier, BOT_MAGIC

if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.join(os.path.dirname(sys.executable), 'data')
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(_APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(_APP_DIR, 'config.json')

DEFAULT_SERVER_URL = 'https://signalserver-6iumv5b0.on-forge.com'

# Available bots that can send signals
AVAILABLE_BOTS = ['IASMC', 'HybridSMC']

LANG = {
    'en': {
        'title': 'SIGNAL COPIER', 'help_btn': '  ? How to use  ',
        'mt5_frame': 'MetaTrader 5', 'mt5_path': 'MT5 Path:', 'browse': 'Browse',
        'path_hint': 'Leave empty to auto-detect the running terminal',
        'connect': 'Connect', 'account': 'Account:', 'server': 'Server:',
        'balance': 'Balance:', 'equity': 'Equity:', 'positions': 'Positions:',
        'searching': '  Searching...', 'connected': '  Connected',
        'not_found': '  Not found — open MT5 and login first',
        'sources_frame': 'Signal Sources',
        'sources_hint': 'Select which bots to copy signals from:',
        'server_frame': 'Signal Server',
        'settings_frame': 'Trading Settings',
        'use_signal': "Use signal's suggested risk (ignore custom settings below)",
        'risk_pct': 'Risk %:', 'max_pos': 'Max positions:', 'max_sym': 'Max per symbol:',
        'start': '  START  ', 'stop': '  STOP  ',
        'stopped': 'STOPPED', 'starting': 'STARTING...', 'running': 'RUNNING',
        'log_frame': 'Signal Log',
        'mt5_log': 'MT5 connected: {} @ {}',
        'mt5_please': 'Please open MetaTrader 5 and login, then click Connect.',
        'mt5_err': 'MT5 not connected.\n\nOpen MetaTrader 5, login, then click Connect.',
        'no_bots_err': 'No signal sources selected.\n\nSelect at least one bot to copy from.',
        'no_url_err': 'Server URL is required.',
        'help_title': 'How to Use', 'got_it': 'Got it!',
        'help_text': """HOW TO USE SIGNAL COPIER

STEP 1 - Choose your MT5 terminal
   Click "Browse" and select terminal64.exe.
   Leave empty to auto-detect.

STEP 2 - Open MetaTrader 5 and login
   Login to your account (demo or real).
   Enable AutoTrading (button in toolbar).

STEP 3 - Connect
   Click "Connect". Account info will appear.

STEP 4 - Select signal sources
   Check which bots you want to copy from:
   - IASMC: SMC strategy (forex + indices + gold)
   - HybridSMC: Hybrid SMC strategy (forex + indices)
   Positions are tracked per-bot for correct management.

STEP 5 - Configure settings
   Check "Use signal's suggested risk" or
   set your own risk %, max positions.

STEP 6 - Start
   Click START. Signals will be copied automatically
   from the signal server.

SIGNALS: Open, Close, SL Modify, Partial TP, Portfolio TP
Each bot's positions are managed independently.
""",
    },
    'it': {
        'title': 'SIGNAL COPIER', 'help_btn': '  ? Come usare  ',
        'mt5_frame': 'MetaTrader 5', 'mt5_path': 'Percorso MT5:', 'browse': 'Sfoglia',
        'path_hint': 'Lascia vuoto per rilevamento automatico',
        'connect': 'Connetti', 'account': 'Conto:', 'server': 'Server:',
        'balance': 'Saldo:', 'equity': 'Equity:', 'positions': 'Posizioni:',
        'searching': '  Ricerca...', 'connected': '  Connesso',
        'not_found': '  Non trovato — apri MT5 e fai login',
        'sources_frame': 'Fonti Segnali',
        'sources_hint': 'Seleziona da quali bot copiare i segnali:',
        'server_frame': 'Server Segnali',
        'settings_frame': 'Impostazioni Trading',
        'use_signal': "Usa il rischio suggerito dal segnale",
        'risk_pct': 'Rischio %:', 'max_pos': 'Max posizioni:', 'max_sym': 'Max per simbolo:',
        'start': '  AVVIA  ', 'stop': '  FERMA  ',
        'stopped': 'FERMO', 'starting': 'AVVIO...', 'running': 'ATTIVO',
        'log_frame': 'Log Segnali',
        'mt5_log': 'MT5 connesso: {} @ {}',
        'mt5_please': 'Apri MetaTrader 5, fai login e clicca Connetti.',
        'mt5_err': 'MT5 non connesso.\n\nApri MetaTrader 5, fai login e clicca Connetti.',
        'no_bots_err': 'Nessuna fonte segnali selezionata.\n\nSeleziona almeno un bot.',
        'no_url_err': 'URL del server richiesto.',
        'help_title': 'Come Usare', 'got_it': 'Capito!',
        'help_text': """COME USARE SIGNAL COPIER

PASSO 1 - Scegli il terminale MT5
   Clicca "Sfoglia" e seleziona terminal64.exe.
   Lascia vuoto per rilevamento automatico.

PASSO 2 - Apri MetaTrader 5 e fai login
   Fai login nel tuo conto (demo o reale).
   Attiva AutoTrading (pulsante in alto).

PASSO 3 - Connetti
   Clicca "Connetti". Le info conto appariranno.

PASSO 4 - Seleziona fonti segnali
   Spunta i bot da cui copiare:
   - IASMC: strategia SMC (forex + indici + oro)
   - HybridSMC: strategia SMC ibrida (forex + indici)
   Le posizioni sono tracciate per bot.

PASSO 5 - Configura impostazioni
   Spunta "Usa rischio suggerito" oppure
   imposta rischio %, max posizioni.

PASSO 6 - Avvia
   Clicca AVVIA. I segnali verranno copiati
   automaticamente dal server.

SEGNALI: Apertura, Chiusura, Modifica SL, TP Parziale, Portfolio TP
Le posizioni di ogni bot sono gestite indipendentemente.
""",
    },
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'trading': {
            'use_signal_settings': True,
            'custom_risk_pct': 1.0,
            'max_positions': 0,
            'max_per_symbol': 1,
        },
        'enabled_bots': ['IASMC', 'HybridSMC'],
        'server': {'url': DEFAULT_SERVER_URL},
    }


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class SignalCopierGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Signal Copier")
        w, h = 620, 520
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(500, 400)
        self.root.configure(bg='#1a1a2e')
        self.root.resizable(True, True)

        self.config = load_config()
        self.copier = None
        self.copier_thread = None
        self.loop = None
        self.account_info = None
        self.connected = False
        self.lang = self.config.get('language', 'en')
        self.t = LANG[self.lang]

        # Bot checkbox variables
        self.bot_vars = {}
        enabled = self.config.get('enabled_bots', ['IASMC', 'HybridSMC'])
        for bot in AVAILABLE_BOTS:
            self.bot_vars[bot] = tk.BooleanVar(value=(bot in enabled))

        self._build_ui()
        self._try_connect_mt5()
        self._update_loop()

    def _build_ui(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('TFrame', background='#1a1a2e')
        s.configure('TLabel', background='#1a1a2e', foreground='#e0e0e0', font=('Segoe UI', 9))
        s.configure('Title.TLabel', background='#1a1a2e', foreground='#00ff88', font=('Segoe UI', 14, 'bold'))
        s.configure('Status.TLabel', background='#1a1a2e', foreground='#ffaa00', font=('Segoe UI', 9, 'bold'))
        s.configure('TLabelframe', background='#1a1a2e', foreground='#e0e0e0')
        s.configure('TLabelframe.Label', background='#1a1a2e', foreground='#e0e0e0', font=('Segoe UI', 9, 'bold'))
        s.configure('TCheckbutton', background='#1a1a2e', foreground='#e0e0e0')
        s.configure('Bot.TCheckbutton', background='#1a1a2e', foreground='#00ccff', font=('Segoe UI', 9, 'bold'))

        # -- Title + Lang + Help --
        top = ttk.Frame(self.root); top.pack(fill='x', padx=10, pady=(8, 4))
        self.w_title = ttk.Label(top, text=self.t['title'], style='Title.TLabel'); self.w_title.pack(side='left')
        self.w_help = ttk.Button(top, text=self.t['help_btn'], command=self._show_help); self.w_help.pack(side='right')
        ttk.Button(top, text="IT", width=3, command=lambda: self._set_lang('it')).pack(side='right', padx=2)
        ttk.Button(top, text="EN", width=3, command=lambda: self._set_lang('en')).pack(side='right', padx=2)

        # -- MT5 --
        self.w_mt5f = ttk.LabelFrame(self.root, text=self.t['mt5_frame'], padding=6); self.w_mt5f.pack(fill='x', padx=10, pady=3)
        pf = ttk.Frame(self.w_mt5f); pf.pack(fill='x', pady=(0, 3))
        self.w_pathlbl = ttk.Label(pf, text=self.t['mt5_path']); self.w_pathlbl.pack(side='left')
        self.mt5_path_var = tk.StringVar(value=self.config.get('mt5_path', ''))
        ttk.Entry(pf, textvariable=self.mt5_path_var, width=45).pack(side='left', padx=5, fill='x', expand=True)
        self.w_browse = ttk.Button(pf, text=self.t['browse'], command=self._browse_mt5); self.w_browse.pack(side='left')
        self.w_hint = ttk.Label(self.w_mt5f, text=self.t['path_hint'], foreground='#888', font=('Segoe UI', 8)); self.w_hint.pack(anchor='w')

        ig = ttk.Frame(self.w_mt5f); ig.pack(fill='x', pady=(3, 0))
        self.mt5_status = ttk.Label(ig, text=self.t['searching'], style='Status.TLabel'); self.mt5_status.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 3))
        self.w_acclbl = ttk.Label(ig, text=self.t['account']); self.w_acclbl.grid(row=1, column=0, sticky='w')
        self.mt5_account = ttk.Label(ig, text="--"); self.mt5_account.grid(row=1, column=1, sticky='w', padx=(5, 15))
        self.w_srvlbl = ttk.Label(ig, text=self.t['server']); self.w_srvlbl.grid(row=1, column=2, sticky='w')
        self.mt5_server = ttk.Label(ig, text="--"); self.mt5_server.grid(row=1, column=3, sticky='w', padx=(5, 0))
        self.w_ballbl = ttk.Label(ig, text=self.t['balance']); self.w_ballbl.grid(row=2, column=0, sticky='w')
        self.mt5_balance = ttk.Label(ig, text="--"); self.mt5_balance.grid(row=2, column=1, sticky='w', padx=(5, 15))
        self.w_eqlbl = ttk.Label(ig, text=self.t['equity']); self.w_eqlbl.grid(row=2, column=2, sticky='w')
        self.mt5_equity = ttk.Label(ig, text="--"); self.mt5_equity.grid(row=2, column=3, sticky='w', padx=(5, 0))
        self.w_poslbl = ttk.Label(ig, text=self.t['positions']); self.w_poslbl.grid(row=2, column=4, sticky='w', padx=(15, 0))
        self.mt5_positions = ttk.Label(ig, text="--"); self.mt5_positions.grid(row=2, column=5, sticky='w', padx=(5, 0))
        self.w_conn = ttk.Button(self.w_mt5f, text=self.t['connect'], command=self._try_connect_mt5); self.w_conn.pack(anchor='e', pady=(3, 0))

        # -- Signal Sources + Settings (combined row) --
        mid = ttk.Frame(self.root); mid.pack(fill='x', padx=10, pady=3)

        self.w_srcf = ttk.LabelFrame(mid, text=self.t['sources_frame'], padding=6); self.w_srcf.pack(side='left', fill='both', expand=True, padx=(0, 3))
        self.bot_checkboxes = {}
        bf_bots = ttk.Frame(self.w_srcf); bf_bots.pack(fill='x')
        for i, bot in enumerate(AVAILABLE_BOTS):
            cb = ttk.Checkbutton(bf_bots, text=bot, variable=self.bot_vars[bot], style='Bot.TCheckbutton')
            cb.grid(row=0, column=i, sticky='w', padx=(0, 15))
            self.bot_checkboxes[bot] = cb

        self.w_setf = ttk.LabelFrame(mid, text=self.t['settings_frame'], padding=6); self.w_setf.pack(side='left', fill='both', expand=True, padx=(3, 0))
        self.use_signal_var = tk.BooleanVar(value=self.config['trading'].get('use_signal_settings', True))
        self.w_usesig = ttk.Checkbutton(self.w_setf, text=self.t['use_signal'], variable=self.use_signal_var, command=self._toggle_custom)
        self.w_usesig.pack(anchor='w')
        cf = ttk.Frame(self.w_setf); cf.pack(fill='x', pady=(3, 0)); self.custom_frame = cf
        self.w_risklbl = ttk.Label(cf, text=self.t['risk_pct']); self.w_risklbl.grid(row=0, column=0, sticky='w', padx=(0, 3))
        self.risk_var = tk.DoubleVar(value=self.config['trading'].get('custom_risk_pct', 1.0))
        ttk.Entry(cf, textvariable=self.risk_var, width=6).grid(row=0, column=1, sticky='w')
        self.w_mposlbl = ttk.Label(cf, text=self.t['max_pos']); self.w_mposlbl.grid(row=0, column=2, sticky='w', padx=(10, 3))
        self.maxpos_var = tk.IntVar(value=self.config['trading'].get('max_positions', 0))
        ttk.Entry(cf, textvariable=self.maxpos_var, width=4).grid(row=0, column=3, sticky='w')
        self.w_msymlbl = ttk.Label(cf, text=self.t['max_sym']); self.w_msymlbl.grid(row=0, column=4, sticky='w', padx=(10, 3))
        self.maxsym_var = tk.IntVar(value=self.config['trading'].get('max_per_symbol', 1))
        ttk.Entry(cf, textvariable=self.maxsym_var, width=4).grid(row=0, column=5, sticky='w')
        self._toggle_custom()

        # -- Server URL (hidden, use default) --
        self.server_url_var = tk.StringVar(value=self.config.get('server', {}).get('url', DEFAULT_SERVER_URL))

        # -- Buttons --
        btf = ttk.Frame(self.root); btf.pack(fill='x', padx=10, pady=3)
        self.start_btn = ttk.Button(btf, text=self.t['start'], command=self._start_copier); self.start_btn.pack(side='left', padx=5)
        self.stop_btn = ttk.Button(btf, text=self.t['stop'], command=self._stop_copier, state='disabled'); self.stop_btn.pack(side='left', padx=5)
        self.copier_status = ttk.Label(btf, text=self.t['stopped'], style='Status.TLabel'); self.copier_status.pack(side='right', padx=5)

        # -- Log (takes all remaining space) --
        self.w_logf = ttk.LabelFrame(self.root, text=self.t['log_frame'], padding=5); self.w_logf.pack(fill='both', expand=True, padx=10, pady=(3, 8))
        self.log_text = scrolledtext.ScrolledText(self.w_logf, height=10, bg='#0d1117', fg='#c9d1d9', font=('Consolas', 9), insertbackground='white', wrap='word')
        self.log_text.pack(fill='both', expand=True)

    # -- Language switch --
    def _set_lang(self, lang):
        self.lang = lang
        self.t = LANG[lang]
        self.config['language'] = lang
        save_config(self.config)
        self.w_title.configure(text=self.t['title'])
        self.w_help.configure(text=self.t['help_btn'])
        self.w_mt5f.configure(text=self.t['mt5_frame'])
        self.w_pathlbl.configure(text=self.t['mt5_path'])
        self.w_browse.configure(text=self.t['browse'])
        self.w_hint.configure(text=self.t['path_hint'])
        self.w_conn.configure(text=self.t['connect'])
        self.w_acclbl.configure(text=self.t['account'])
        self.w_srvlbl.configure(text=self.t['server'])
        self.w_ballbl.configure(text=self.t['balance'])
        self.w_eqlbl.configure(text=self.t['equity'])
        self.w_poslbl.configure(text=self.t['positions'])
        self.w_srcf.configure(text=self.t['sources_frame'])
        self.w_setf.configure(text=self.t['settings_frame'])
        self.w_usesig.configure(text=self.t['use_signal'])
        self.w_risklbl.configure(text=self.t['risk_pct'])
        self.w_mposlbl.configure(text=self.t['max_pos'])
        self.w_msymlbl.configure(text=self.t['max_sym'])
        self.start_btn.configure(text=self.t['start'])
        self.stop_btn.configure(text=self.t['stop'])
        self.w_logf.configure(text=self.t['log_frame'])
        if self.connected:
            self.mt5_status.configure(text=self.t['connected'])
        else:
            self.mt5_status.configure(text=self.t['not_found'])

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title(self.t['help_title'])
        win.geometry("480x500")
        win.configure(bg='#1a1a2e')
        win.resizable(False, False)
        txt = scrolledtext.ScrolledText(win, bg='#0d1117', fg='#c9d1d9', font=('Segoe UI', 10), wrap='word', padx=15, pady=15)
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('1.0', self.t['help_text'])
        txt.configure(state='disabled')
        ttk.Button(win, text=self.t['got_it'], command=win.destroy).pack(pady=(0, 10))

    def _toggle_custom(self):
        state = 'disabled' if self.use_signal_var.get() else 'normal'
        for child in self.custom_frame.winfo_children():
            try: child.configure(state=state)
            except: pass

    def _browse_mt5(self):
        path = filedialog.askopenfilename(title="Select terminal64.exe", filetypes=[("MetaTrader 5", "terminal64.exe"), ("All", "*.*")], initialdir="C:/Program Files")
        if path:
            self.mt5_path_var.set(path)
            self.config['mt5_path'] = path
            save_config(self.config)
            self._try_connect_mt5()

    def _try_connect_mt5(self):
        path = self.mt5_path_var.get().strip() or None
        self.account_info = auto_connect(path)
        if self.account_info:
            self.connected = True
            self.mt5_status.configure(text=self.t['connected'], foreground='#00ff88')
            self.mt5_account.configure(text=str(self.account_info.login))
            self.mt5_server.configure(text=self.account_info.server)
            self.mt5_balance.configure(text=f"{self.account_info.balance:.2f} {self.account_info.currency}")
            self.mt5_equity.configure(text=f"{self.account_info.equity:.2f} {self.account_info.currency}")
            copier_pos = sum(len(get_open_positions(m)) for m in BOT_MAGIC.values())
            self.mt5_positions.configure(text=str(copier_pos))
            self._log(self.t['mt5_log'].format(self.account_info.login, self.account_info.server))
        else:
            self.connected = False
            self.mt5_status.configure(text=self.t['not_found'], foreground='#ff4444')
            self._log(self.t['mt5_please'])

    def _get_enabled_bots(self) -> list:
        return [bot for bot, var in self.bot_vars.items() if var.get()]

    def _update_loop(self):
        if self.connected:
            try:
                eq = get_account_equity()
                if eq > 0:
                    self.mt5_equity.configure(text=f"{eq:.2f}")
                    copier_pos = sum(len(get_open_positions(m)) for m in BOT_MAGIC.values())
                    self.mt5_positions.configure(text=str(copier_pos))
            except: pass
        self.config['trading'] = {
            'use_signal_settings': self.use_signal_var.get(),
            'custom_risk_pct': self.risk_var.get(),
            'max_positions': self.maxpos_var.get(),
            'max_per_symbol': self.maxsym_var.get(),
        }
        self.config['enabled_bots'] = self._get_enabled_bots()
        self.config['server'] = {'url': self.server_url_var.get().strip()}
        self.root.after(5000, self._update_loop)

    def _log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{ts}] {msg}\n")
        self.log_text.see('end')

    def _start_copier(self):
        if not self.connected:
            messagebox.showerror("Error", self.t['mt5_err'])
            return
        enabled = self._get_enabled_bots()
        if not enabled:
            messagebox.showerror("Error", self.t['no_bots_err'])
            return

        self.config['server'] = {'url': self.server_url_var.get().strip() or DEFAULT_SERVER_URL}
        self.config['mt5_path'] = self.mt5_path_var.get().strip()
        self.config['enabled_bots'] = enabled
        save_config(self.config)

        self.copier = SignalCopier(
            config=self.config,
            on_log=lambda m: self.root.after(0, self._log, m),
            on_trade=lambda t: self.root.after(0, self._on_trade, t),
            on_status=lambda s: self.root.after(0, self._on_status, s),
        )
        self.loop = asyncio.new_event_loop()
        self.copier_thread = threading.Thread(
            target=lambda: (asyncio.set_event_loop(self.loop), self.loop.run_until_complete(self.copier.start())),
            daemon=True,
        )
        self.copier_thread.start()
        self.start_btn.configure(state='disabled'); self.stop_btn.configure(state='normal')
        for cb in self.bot_checkboxes.values():
            cb.configure(state='disabled')
        self.copier_status.configure(text=self.t['starting'], foreground='#ffaa00')

    def _stop_copier(self):
        if self.copier and self.loop:
            asyncio.run_coroutine_threadsafe(self.copier.stop(), self.loop)
        self.start_btn.configure(state='normal'); self.stop_btn.configure(state='disabled')
        for cb in self.bot_checkboxes.values():
            cb.configure(state='normal')
        self.copier_status.configure(text=self.t['stopped'], foreground='#ffaa00')

    def _on_trade(self, t):
        src = t.get('source', '?')
        self._log(f"[{src}] TRADE: {t['direction'].upper()} {t['symbol']} lot={t['lot']} @ {t['entry']}")

    def _on_status(self, status):
        if status == 'running':
            self.copier_status.configure(text=self.t['running'], foreground='#00ff88')
        else:
            self.copier_status.configure(text=self.t['stopped'], foreground='#ffaa00')
            self.start_btn.configure(state='normal'); self.stop_btn.configure(state='disabled')
            for cb in self.bot_checkboxes.values():
                cb.configure(state='normal')

    def run(self):
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if self.copier: self._stop_copier()
        disconnect()
        self.root.destroy()


if __name__ == '__main__':
    import logging
    _log_dir = os.path.join(_APP_DIR, 'logs')
    os.makedirs(_log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(_log_dir, 'signal_copier.log'), encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )
    SignalCopierGUI().run()
