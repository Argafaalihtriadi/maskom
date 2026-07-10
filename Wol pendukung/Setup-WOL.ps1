<#
==============================================================================
 Setup-WOL.ps1
 Script pendukung TERPISAH dari SpecWol (main.py / main.exe).
 Fungsi: Audit & perbaiki pengaturan Windows yang dibutuhkan agar
 Wake-on-LAN (WOL) berfungsi di komputer ini, meliputi:
   1. Power Management adapter jaringan (Allow this device to wake the
      computer, Only allow a magic packet to wake the computer)
   2. Advanced Property NIC: Wake on Magic Packet, Energy Efficient
      Ethernet / Green Ethernet, Shutdown Wake-On-Lan (kalau tersedia)
   3. Fast Startup Windows (dimatikan, karena bisa mengganggu WOL saat
      komputer di-shutdown biasa)

 CARA PAKAI (WAJIB dijalankan sebagai Administrator):
   1. Klik kanan PowerShell -> "Run as Administrator"
   2. Jalankan salah satu:

      # Audit saja, tidak mengubah apa pun (aman, lihat status dulu)
      powershell -ExecutionPolicy Bypass -File .\Setup-WOL.ps1 -AuditOnly

      # Audit sekaligus otomatis perbaiki setting yang belum sesuai
      powershell -ExecutionPolicy Bypass -File .\Setup-WOL.ps1

   3. Hasil audit juga disimpan ke file log di folder yang sama:
      WOL-Report-<HOSTNAME>-<tanggal>.json
==============================================================================
#>

param(
    [switch]$AuditOnly,
    [switch]$KeepFastStartup   # gunakan switch ini jika TIDAK mau Fast Startup dimatikan
)

# --------------------------------------------------------------------------
# 0. Pastikan dijalankan sebagai Administrator
# --------------------------------------------------------------------------
function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "[ERROR] Script ini HARUS dijalankan sebagai Administrator." -ForegroundColor Red
    Write-Host "Klik kanan PowerShell -> 'Run as Administrator', lalu jalankan ulang." -ForegroundColor Yellow
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " SETUP-WOL - Audit & Perbaikan Setting Wake-on-LAN" -ForegroundColor Cyan
Write-Host " Mode: $(if ($AuditOnly) {'AUDIT ONLY (tidak mengubah apa pun)'} else {'AUDIT + AUTO FIX'})" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$report = [ordered]@{
    Hostname  = $env:COMPUTERNAME
    Timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Mode      = if ($AuditOnly) { "AuditOnly" } else { "AuditAndFix" }
    Adapters  = @()
    FastStartup = $null
}

# --------------------------------------------------------------------------
# 1. Ambil daftar adapter jaringan fisik (bukan virtual/Bluetooth/loopback)
# --------------------------------------------------------------------------
$adapters = Get-NetAdapter | Where-Object {
    $_.HardwareInterface -eq $true -and
    $_.Virtual -eq $false -and
    $_.InterfaceDescription -notmatch "Bluetooth|Virtual|Loopback|WAN Miniport"
}

if (-not $adapters) {
    Write-Host "[WARNING] Tidak ditemukan adapter jaringan fisik di komputer ini." -ForegroundColor Yellow
}

foreach ($adapter in $adapters) {
    $name = $adapter.Name
    $desc = $adapter.InterfaceDescription
    Write-Host "`n--- Adapter: $name ($desc) ---" -ForegroundColor Green

    $adapterReport = [ordered]@{
        Name                 = $name
        Description          = $desc
        Status               = $adapter.Status
        WakeOnMagicPacket    = "Tidak diketahui"
        DeviceWakeEnabled    = "Tidak diketahui"
        EnergyEfficientEth   = "Tidak diketahui"
        Actions              = @()
    }

    # ---- 1a. Set-NetAdapterPowerManagement (Wake on Magic Packet) ----
    try {
        $pm = Get-NetAdapterPowerManagement -Name $name -ErrorAction Stop
        $adapterReport.WakeOnMagicPacket = $pm.WakeOnMagicPacket

        if ($pm.WakeOnMagicPacket -ne "Enabled") {
            if (-not $AuditOnly) {
                Set-NetAdapterPowerManagement -Name $name -WakeOnMagicPacket Enabled -ErrorAction Stop
                $adapterReport.WakeOnMagicPacket = "Enabled (diperbaiki)"
                $adapterReport.Actions += "WakeOnMagicPacket diaktifkan"
                Write-Host "  [FIX] Wake on Magic Packet -> Enabled" -ForegroundColor Yellow
            } else {
                Write-Host "  [AUDIT] Wake on Magic Packet: DISABLED (perlu diaktifkan)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [OK] Wake on Magic Packet: Enabled" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  [SKIP] Adapter ini tidak mendukung cmdlet Power Management (driver tidak expose fitur ini)." -ForegroundColor DarkGray
    }

    # ---- 1b. Advanced Properties: EEE / Green Ethernet, Shutdown WOL ----
    $advProps = Get-NetAdapterAdvancedProperty -Name $name -ErrorAction SilentlyContinue
    $eeeNames = @("Energy Efficient Ethernet", "Green Ethernet", "Advanced EEE", "EEE")
    $wolNames = @("Wake on Magic Packet", "Shutdown Wake-On-Lan", "Wake-On-Lan", "WOL & Shutdown Link Speed")

    foreach ($prop in $advProps) {
        if ($eeeNames -contains $prop.DisplayName) {
            $adapterReport.EnergyEfficientEth = $prop.DisplayValue
            if ($prop.DisplayValue -notmatch "Disabled|Off") {
                if (-not $AuditOnly) {
                    try {
                        Set-NetAdapterAdvancedProperty -Name $name -DisplayName $prop.DisplayName -DisplayValue "Disabled" -ErrorAction Stop
                        $adapterReport.Actions += "$($prop.DisplayName) dinonaktifkan"
                        Write-Host "  [FIX] $($prop.DisplayName) -> Disabled" -ForegroundColor Yellow
                    } catch {
                        Write-Host "  [WARN] Gagal mengubah '$($prop.DisplayName)' otomatis, silakan set manual di Device Manager." -ForegroundColor DarkYellow
                    }
                } else {
                    Write-Host "  [AUDIT] $($prop.DisplayName): $($prop.DisplayValue) (sebaiknya Disabled)" -ForegroundColor Yellow
                }
            } else {
                Write-Host "  [OK] $($prop.DisplayName): Disabled" -ForegroundColor Gray
            }
        }
        if ($wolNames -contains $prop.DisplayName -and $prop.DisplayValue -match "Disabled|Off") {
            if (-not $AuditOnly) {
                try {
                    $enabledValue = ($prop.ValidDisplayValues | Where-Object { $_ -match "Enabled|On" } | Select-Object -First 1)
                    if ($enabledValue) {
                        Set-NetAdapterAdvancedProperty -Name $name -DisplayName $prop.DisplayName -DisplayValue $enabledValue -ErrorAction Stop
                        $adapterReport.Actions += "$($prop.DisplayName) diaktifkan"
                        Write-Host "  [FIX] $($prop.DisplayName) -> $enabledValue" -ForegroundColor Yellow
                    }
                } catch {
                    Write-Host "  [WARN] Gagal mengubah '$($prop.DisplayName)' otomatis, silakan set manual di Device Manager." -ForegroundColor DarkYellow
                }
            } else {
                Write-Host "  [AUDIT] $($prop.DisplayName): $($prop.DisplayValue) (sebaiknya Enabled)" -ForegroundColor Yellow
            }
        }
    }

    # ---- 1c. Tandai device sebagai wake source di level OS (setara centang
    #          "Allow this device to wake the computer" di Device Manager) ----
    $wakeArmedList = (powercfg /devicequery wake_armed) -join "`n"
    if ($wakeArmedList -match [Regex]::Escape($desc)) {
        $adapterReport.DeviceWakeEnabled = $true
        Write-Host "  [OK] Device sudah diizinkan membangunkan komputer (powercfg wake_armed)" -ForegroundColor Gray
    } else {
        $adapterReport.DeviceWakeEnabled = $false
        if (-not $AuditOnly) {
            try {
                powercfg /deviceenablewake "$desc" | Out-Null
                $adapterReport.Actions += "Diizinkan sebagai wake source (powercfg /deviceenablewake)"
                Write-Host "  [FIX] Device diizinkan sebagai wake source" -ForegroundColor Yellow
            } catch {
                Write-Host "  [WARN] Gagal set wake source otomatis untuk '$desc'." -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "  [AUDIT] Device BELUM diizinkan sebagai wake source" -ForegroundColor Yellow
        }
    }

    $report.Adapters += $adapterReport
}

# --------------------------------------------------------------------------
# 2. Fast Startup (HiberbootEnabled)
# --------------------------------------------------------------------------
Write-Host "`n--- Fast Startup Windows ---" -ForegroundColor Green
$powerKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power"
$hiberboot = (Get-ItemProperty -Path $powerKey -Name HiberbootEnabled -ErrorAction SilentlyContinue).HiberbootEnabled

if ($null -eq $hiberboot) {
    Write-Host "  [INFO] Fast Startup tidak terdeteksi di registry (kemungkinan hibernation memang nonaktif)." -ForegroundColor DarkGray
    $report.FastStartup = "Tidak terdeteksi"
} elseif ($hiberboot -eq 1) {
    $report.FastStartup = "Enabled"
    if (-not $AuditOnly -and -not $KeepFastStartup) {
        Set-ItemProperty -Path $powerKey -Name HiberbootEnabled -Value 0
        $report.FastStartup = "Enabled (dimatikan sekarang)"
        Write-Host "  [FIX] Fast Startup -> Disabled" -ForegroundColor Yellow
    } else {
        Write-Host "  [AUDIT] Fast Startup: ENABLED (disarankan dimatikan agar WOL setelah Shutdown lebih stabil)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [OK] Fast Startup: Disabled" -ForegroundColor Gray
    $report.FastStartup = "Disabled"
}

# --------------------------------------------------------------------------
# 3. Simpan laporan JSON lokal
# --------------------------------------------------------------------------
$reportFile = Join-Path -Path $PSScriptRoot -ChildPath "WOL-Report-$($env:COMPUTERNAME)-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
$report | ConvertTo-Json -Depth 5 | Out-File -FilePath $reportFile -Encoding UTF8

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " Selesai. Laporan disimpan di:" -ForegroundColor Cyan
Write-Host " $reportFile" -ForegroundColor White
if ($AuditOnly) {
    Write-Host "`n Mode ini hanya AUDIT. Jalankan ulang TANPA -AuditOnly untuk memperbaiki otomatis." -ForegroundColor Yellow
} else {
    Write-Host "`n Disarankan RESTART komputer ini agar seluruh perubahan berlaku penuh." -ForegroundColor Yellow
}
Write-Host "==========================================================" -ForegroundColor Cyan
