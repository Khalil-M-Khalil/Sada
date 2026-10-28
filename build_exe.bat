@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
if errorlevel 1 goto fail
python -m PyInstaller --onefile --name Sada --icon "brand\sada.ico" --add-data "index.html;." server.py
if errorlevel 1 goto fail
echo.
echo Done: %~dp0dist\Sada.exe
pause
exit /b 0
:fail
echo.
echo BUILD FAILED - read the messages above.
pause
exit /b 1
