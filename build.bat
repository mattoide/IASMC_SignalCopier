@echo off
echo Building SignalCopier.exe...
pyinstaller --onefile --windowed --name SignalCopier --icon=icon.ico gui.py --add-data "config.json;." --hidden-import=MetaTrader5 --hidden-import=telethon
echo Done! Check dist\SignalCopier.exe
pause
