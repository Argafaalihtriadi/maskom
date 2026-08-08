#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installer Agen MaskomApp — Startup & WebSocket Daemon
    
.DESCRIPTION
    Script ini menyalin main.exe ke folder instalasi, mengonfigurasi IP Server,
    dan mendaftarkannya ke Windows Registry Startup agar agen berjalan otomatis
    di latar belakang setiap kali Windows boot.
    
.PARAMETER ServerIP
    Alamat IP server MaskomApp (default: 192.168.33.181)
    
.PARAMETER ServerPort
    Port server MaskomApp (default: 3000)
    
.PARAMETER AgentToken
    Token keamanan agen (default: maskom-agent-2024)

.EXAMPLE
    .\install-agent.ps1 -ServerIP 192.168.33.181 -ServerPort 3000
#>

param (
    [string]$ServerIP    = "192.168.33.181",
    [int]   $ServerPort  = 3000,
    [string]$AgentToken  = "maskom-agent-2024"
)

# =====================================================
# KONFIGURASI
# =====================================================
$INSTALL_DIR    = "C:\Program Files\MaskomAgent"
$EXE_NAME       = "main.exe"
$STARTUP_NAME   = "MaskomAgent"
$SERVER_URL     = "ws://${ServerIP}:${ServerPort}"
$SOURCE_EXE     = Join-Path $PSScriptRoot $EXE_NAME
$ENV_FILE       = Join-Path $INSTALL_DIR ".env"

# =====================================================
# CEK PRASYARAT
# =====================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLER AGEN MaskomApp v1.0                            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Cek apakah main.exe ada di folder yang sama dengan script ini
if (-not (Test-Path $SOURCE_EXE)) {
    Write-Host "[ERROR] File '$EXE_NAME' tidak ditemukan di:" -ForegroundColor Red
    Write-Host "        $PSScriptRoot" -ForegroundColor Red
    Write-Host ""
    Write-Host "Pastikan file '$EXE_NAME' diletakkan di folder yang sama" -ForegroundColor Yellow
    Write-Host "dengan script ini sebelum menjalankannya." -ForegroundColor Yellow
    Pause
    exit 1
}

Write-Host "[1/5] Memeriksa direktori instalasi..." -ForegroundColor Yellow

# =====================================================
# 1. BUAT DIREKTORI INSTALASI
# =====================================================
if (-not (Test-Path $INSTALL_DIR)) {
    New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
    Write-Host "      Direktori dibuat: $INSTALL_DIR" -ForegroundColor Green
} else {
    Write-Host "      Direktori sudah ada: $INSTALL_DIR" -ForegroundColor Green
}

# =====================================================
# 2. SALIN FILE EXE KE INSTALL DIR
# =====================================================
Write-Host "[2/5] Menyalin agen ke direktori instalasi..." -ForegroundColor Yellow

# Hentikan proses agen lama jika ada
$existingProc = Get-Process -Name "main" -ErrorAction SilentlyContinue
if ($existingProc) {
    Write-Host "      Menghentikan proses agen lama (PID: $($existingProc.Id))..." -ForegroundColor Gray
    Stop-Process -Id $existingProc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Copy-Item -Path $SOURCE_EXE -Destination "$INSTALL_DIR\$EXE_NAME" -Force
Write-Host "      Agen disalin ke: $INSTALL_DIR\$EXE_NAME" -ForegroundColor Green

# =====================================================
# 3. TULIS FILE KONFIGURASI .env
# =====================================================
Write-Host "[3/5] Membuat file konfigurasi agen..." -ForegroundColor Yellow

$envContent = @"
# ============================================
# Konfigurasi Agen MaskomApp
# Dihasilkan otomatis oleh install-agent.ps1
# ============================================
MASKOM_SERVER_URL=$SERVER_URL
MASKOM_AGENT_TOKEN=$AgentToken
"@

Set-Content -Path $ENV_FILE -Value $envContent -Encoding UTF8
Write-Host "      File konfigurasi dibuat: $ENV_FILE" -ForegroundColor Green
Write-Host "      URL Server WebSocket    : $SERVER_URL" -ForegroundColor Green

# =====================================================
# 4. DAFTARKAN KE REGISTRY STARTUP
# =====================================================
Write-Host "[4/5] Mendaftarkan ke Windows Registry Startup..." -ForegroundColor Yellow

$startupCmd = "`"$INSTALL_DIR\$EXE_NAME`" --daemon --server $SERVER_URL"
$regPath    = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

try {
    Set-ItemProperty -Path $regPath -Name $STARTUP_NAME -Value $startupCmd -Force
    Write-Host "      Startup entry didaftarkan:" -ForegroundColor Green
    Write-Host "      Nama    : $STARTUP_NAME" -ForegroundColor Green
    Write-Host "      Perintah: $startupCmd" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Gagal mendaftar ke Registry: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "       Agen harus dijalankan secara manual." -ForegroundColor Yellow
}

# =====================================================
# 5. BUKA ATURAN FIREWALL (OUTBOUND)
# =====================================================
Write-Host "[5/5] Mengatur aturan Windows Firewall..." -ForegroundColor Yellow

$fwRuleName  = "MaskomAgent-WebSocket"
$existingRule = Get-NetFirewallRule -DisplayName $fwRuleName -ErrorAction SilentlyContinue

if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $fwRuleName -ErrorAction SilentlyContinue
}

try {
    New-NetFirewallRule `
        -DisplayName $fwRuleName `
        -Direction   Outbound `
        -Protocol    TCP `
        -LocalPort   Any `
        -RemotePort  $ServerPort `
        -Action      Allow `
        -Profile     Any `
        -Program     "$INSTALL_DIR\$EXE_NAME" | Out-Null
    Write-Host "      Aturan firewall outbound ke port $ServerPort diizinkan." -ForegroundColor Green
} catch {
    Write-Host "[WARN] Gagal membuat aturan firewall: $($_.Exception.Message)" -ForegroundColor Yellow
}

# =====================================================
# SELESAI — JALANKAN AGEN SEKARANG
# =====================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  INSTALASI SELESAI!                                        " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Agen akan otomatis aktif saat Windows dinyalakan berikutnya." -ForegroundColor White
Write-Host ""
Write-Host "  Untuk menjalankan agen sekarang tanpa restart Windows," -ForegroundColor White
Write-Host "  tekan Y lalu ENTER. Atau tekan N untuk keluar." -ForegroundColor White
Write-Host ""

$runNow = Read-Host "Jalankan agen sekarang? (Y/N)"
if ($runNow -match "^[Yy]") {
    Write-Host ""
    Write-Host "  Menjalankan MaskomAgent di latar belakang..." -ForegroundColor Cyan
    Start-Process -FilePath "$INSTALL_DIR\$EXE_NAME" `
                  -ArgumentList "--daemon --server $SERVER_URL" `
                  -WindowStyle Hidden
    Write-Host "  Agen berjalan! Terhubung ke: $SERVER_URL" -ForegroundColor Green
}

Write-Host ""
Write-Host "  Untuk memeriksa status agen, buka Task Manager" -ForegroundColor Gray
Write-Host "  dan cari proses bernama 'main'." -ForegroundColor Gray
Write-Host ""
Pause
