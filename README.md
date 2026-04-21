# SignalCopier

Signal copier for MT5. Polls a signal server and executes trades automatically.

## Features
- Polls signal server for IASMC and HybridSMC trading signals
- Auto-detect MT5 terminal or manual path selection
- Signal types: Open, Close, SL Modify, Partial TP, Portfolio TP
- Per-bot position tracking with independent magic numbers
- Configurable risk % or use signal's suggested risk
- DNS-over-HTTPS fallback for VPN environments
- EN/IT language support
- GUI interface (tkinter)
- Standalone .exe (no Python needed)
- **Singleton lock**: only one copier instance per Windows session (prevents duplicate positions from accidental double-launch)

## Usage
1. Open MetaTrader 5 and login
2. Run `python gui.py` or the standalone `.exe`
3. Click Connect, select signal sources, click START

## Build
```
pyinstaller IASMC_SignalCopier.spec
```
Output in `dist/IASMC_SignalCopier.exe`.

