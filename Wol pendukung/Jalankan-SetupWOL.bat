@echo off
REM ==========================================================================
REM  Jalankan-SetupWOL.bat
REM  Launcher untuk Setup-WOL.ps1 - otomatis minta akses Administrator (UAC)
REM  dan menjalankan script PowerShell tanpa perlu setting execution policy
REM  manual.
REM
REM  Cara pakai:
REM    - Taruh file .bat ini di folder YANG SAMA dengan Setup-WOL.ps1
REM    - Double-click file ini
REM    - Klik "Yes" saat muncul prompt UAC
REM
REM  Mode AUDIT ONLY (tidak mengubah apa pun, cuma cek status):
REM    Jalankan lewat cmd:  Jalankan-SetupWOL.bat audit
REM ==========================================================================

setlocal

set "SCRIPT_DIR=%~dp0"
set "PS1_PATH=%SCRIPT_DIR%Setup-WOL.ps1"

REM Cek apakah Setup-WOL.ps1 ada di folder yang sama
if not exist "%PS1_PATH%" (
    echo [ERROR] Tidak ditemukan Setup-WOL.ps1 di folder ini:
    echo         %SCRIPT_DIR%
    echo.
    echo Pastikan Setup-WOL.ps1 ditaruh di folder yang sama dengan file .bat ini.
    pause
    exit /b 1
)

REM Tentukan argumen untuk mode AuditOnly (opsional, ketik "audit" saat run)
set "EXTRA_ARGS="
if /I "%~1"=="audit" set "EXTRA_ARGS=-AuditOnly"

REM Cek apakah sudah berjalan sebagai Administrator
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo [INFO] Meminta akses Administrator, akan muncul jendela konfirmasi UAC...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\" %~1' -Verb RunAs"
    exit /b
)

echo ==========================================================
echo  Menjalankan Setup-WOL.ps1 ...
echo ==========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1_PATH%" %EXTRA_ARGS%

echo.
echo ==========================================================
echo  Selesai. Tekan tombol apa saja untuk menutup jendela ini.
echo ==========================================================
pause >nul
