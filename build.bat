@echo off
echo ============================================================
echo  BCL Parser - Build EXE
echo ============================================================

:: Activate venv
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

set PYTHON=.venv\Scripts\python.exe
set PIP=.venv\Scripts\pip.exe

:: Generate icon.ico
echo Generating icon...
%PYTHON% build_icon.py
if %errorlevel% neq 0 (
    echo ERROR: Icon generation failed.
    pause
    exit /b 1
)

:: Install PyInstaller if not present
%PYTHON% -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    %PIP% install pyinstaller
)

:: Build EXE
echo.
echo Building EXE...

set ADD_DATA_SA=
if exist "src\sheets\service_account.json" (
    set ADD_DATA_SA=--add-data "src\sheets\service_account.json;src\sheets"
)

%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "BCL Parser" ^
    --icon "assets\icon.ico" ^
    %ADD_DATA_SA% ^
    --hidden-import "gspread" ^
    --hidden-import "google.auth" ^
    --hidden-import "google.oauth2" ^
    --hidden-import "keyring" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --collect-all "playwright" ^
    src\main.py

if %errorlevel% == 0 (
    echo.
    echo ============================================================
    echo  SUCCESS: dist\BCL Parser.exe
    echo ============================================================
) else (
    echo.
    echo ERROR: Build failed. Check output above.
)

pause
