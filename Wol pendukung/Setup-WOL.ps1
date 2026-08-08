<#
 ==============================================================================
 Setup-WOL.ps1
 Script pendukung TERPISAH dari SpecWol (main.py / main.exe).
 Fungsi: Audit & perbaiki pengaturan Windows yang dibutuhkan agar
 Wake-on-LAN (WOL) dan Remote Shutdown (shutdown /m) berfungsi, meliputi:
   1. Power Management adapter jaringan (Allow this device to wake the
      computer, Only allow a magic packet to wake the computer)
   2. Advanced Property NIC: Wake on Magic Packet, Energy Efficient
      Ethernet / Green Ethernet, Shutdown Wake-On-Lan (kalau tersedia)
   3. Firewall SMB-In & Remote Registry untuk Remote Shutdown
   4. Remote UAC (LocalAccountTokenFilterPolicy) - dinonaktifkan
   5. Fast Startup Windows (dimatikan, karena bisa mengganggu WOL saat
      komputer di-shutdown biasa)

 CARA PAKAI (WAJIB dijalankan sebagai Administrator):
   1. Klik kanan PowerShell -> "Run as Administrator"
   2. Jalankan salah satu:

      # Audit saja, tidak mengubah apa pun (aman, lihat status dulu)
      powershell -ExecutionPolicy Bypass -File .\Setup-WOL.ps1 -AuditOnly

      # Audit sekaligus otomatis perbaiki setting yang belum sesuai
      powershell -ExecutionPolicy Bypass -File .\Setup-WOL.ps1

      # Tanpa mengubah Fast Startup (jika ingin tetap aktif)
      powershell -ExecutionPolicy Bypass -File .\Setup-WOL.ps1 -KeepFastStartup

   3. Hasil audit juga disimpan ke file log di folder yang sama:
      WOL-Report-<HOSTNAME>-<tanggal>.json
 ==============================================================================
#>

param(
    [switch]$AuditOnly,
    [switch]$KeepFastStartup
)

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

Write-Host "`n--- Remote Shutdown Support (shutdown /m) ---" -ForegroundColor Green

$remoteShutdownReport = [ordered]@{
    FirewallSMB    = "Tidak diketahui"
    RemoteUAC      = "Tidak diketahui"
    RemoteRegistry = "Tidak diketahui"
    Actions        = @()
}

try {
    $fwRules = Get-NetFirewallRule -DisplayGroup "File and Printer Sharing" -ErrorAction Stop
    $smbInRules = $fwRules | Where-Object { $_.Direction -eq "Inbound" -and $_.Enabled -eq $true }
    if ($smbInRules.Count -gt 0) {
        $remoteShutdownReport.FirewallSMB = "Enabled"
        Write-Host "  [OK] Firewall 'File and Printer Sharing (SMB-In)' sudah aktif" -ForegroundColor Gray
    } else {
        $remoteShutdownReport.FirewallSMB = "Disabled"
        if (-not $AuditOnly) {
            try {
                netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes | Out-Null
                $remoteShutdownReport.Actions += "Firewall SMB-In diaktifkan"
                $remoteShutdownReport.FirewallSMB = "Enabled (diperbaiki)"
                Write-Host "  [FIX] Firewall 'File and Printer Sharing' -> Enabled" -ForegroundColor Yellow
            } catch {
                Write-Host "  [WARN] Gagal mengaktifkan firewall rule secara otomatis." -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "  [AUDIT] Firewall 'File and Printer Sharing (SMB-In)': DISABLED (perlu diaktifkan)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  [SKIP] Tidak dapat memeriksa firewall (cmdlet tidak tersedia di Windows versi ini)." -ForegroundColor DarkGray
}

$regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
$filterPolicy = $null
try {
    $filterPolicy = (Get-ItemProperty -Path $regPath -Name LocalAccountTokenFilterPolicy -ErrorAction SilentlyContinue).LocalAccountTokenFilterPolicy
} catch {}

if ($null -eq $filterPolicy) {
    $remoteShutdownReport.RemoteUAC = "NotSet (default: akses hanya untuk domain admin)"
    if (-not $AuditOnly) {
        try {
            New-ItemProperty -Path $regPath -Name LocalAccountTokenFilterPolicy -PropertyType DWord -Value 1 -Force | Out-Null
            $remoteShutdownReport.Actions += "LocalAccountTokenFilterPolicy diatur ke 1 (Remote UAC dinonaktifkan)"
            $remoteShutdownReport.RemoteUAC = "Disabled (diperbaiki)"
            Write-Host "  [FIX] Remote UAC dinonaktifkan (LocalAccountTokenFilterPolicy=1)" -ForegroundColor Yellow
        } catch {
            Write-Host "  [WARN] Gagal mengubah registry LocalAccountTokenFilterPolicy." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  [AUDIT] Remote UAC: NotSet (akses remote dibatasi, sebaiknya set LocalAccountTokenFilterPolicy=1)" -ForegroundColor Yellow
    }
} elseif ($filterPolicy -eq 1) {
    $remoteShutdownReport.RemoteUAC = "Disabled"
    Write-Host "  [OK] Remote UAC sudah dinonaktifkan (LocalAccountTokenFilterPolicy=1)" -ForegroundColor Gray
} else {
    $remoteShutdownReport.RemoteUAC = "Enabled (LocalAccountTokenFilterPolicy=$filterPolicy)"
    if (-not $AuditOnly) {
        try {
            Set-ItemProperty -Path $regPath -Name LocalAccountTokenFilterPolicy -Value 1
            $remoteShutdownReport.Actions += "LocalAccountTokenFilterPolicy diubah ke 1"
            $remoteShutdownReport.RemoteUAC = "Disabled (diperbaiki)"
            Write-Host "  [FIX] LocalAccountTokenFilterPolicy -> 1" -ForegroundColor Yellow
        } catch {
            Write-Host "  [WARN] Gagal mengubah registry." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  [AUDIT] Remote UAC: $($remoteShutdownReport.RemoteUAC) (sebaiknya Disabled)" -ForegroundColor Yellow
    }
}

try {
    $svc = Get-Service -Name RemoteRegistry -ErrorAction Stop
    $remoteShutdownReport.RemoteRegistry = $svc.Status
    if ($svc.StartType -ne [ServiceStartMode]::Automatic) {
        if (-not $AuditOnly) {
            Set-Service -Name RemoteRegistry -StartupType Automatic
            $remoteShutdownReport.Actions += "Remote Registry startup type diubah ke Automatic"
            Write-Host "  [FIX] Remote Registry -> Startup Automatic" -ForegroundColor Yellow
        } else {
            Write-Host "  [AUDIT] Remote Registry: $($svc.Status) (Startup: $($svc.StartType), sebaiknya Automatic)" -ForegroundColor Yellow
        }
    }
    if ($svc.Status -ne [ServiceControllerStatus]::Running) {
        if (-not $AuditOnly) {
            Start-Service -Name RemoteRegistry
            $remoteShutdownReport.Actions += "Remote Registry service dijalankan"
            $remoteShutdownReport.RemoteRegistry = "Running (diperbaiki)"
            Write-Host "  [FIX] Remote Registry -> Running" -ForegroundColor Yellow
        } else {
            Write-Host "  [AUDIT] Remote Registry: $($svc.Status) (perlu dijalankan)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [OK] Remote Registry: Running (Startup: $($svc.StartType))" -ForegroundColor Gray
    }
} catch {
    Write-Host "  [SKIP] Remote Registry service tidak tersedia di Windows versi ini." -ForegroundColor DarkGray
}

$report.RemoteShutdown = $remoteShutdownReport

try {
    $testConn = Test-NetConnection -ComputerName $env:COMPUTERNAME -Port 445 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($testConn) {
        Write-Host "  [OK] Port 445 (SMB) terbuka di komputer ini - siap menerima perintah remote shutdown." -ForegroundColor Gray
    } else {
        Write-Host "  [WARN] Port 445 (SMB) tidak terbuka. Periksa firewall jika remote shutdown gagal." -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "  [SKIP] Tidak dapat tes port 445." -ForegroundColor DarkGray
}

try {
    $blankPw = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name LimitBlankPasswordUse -ErrorAction SilentlyContinue).LimitBlankPasswordUse
    if ($blankPw -eq 0) {
        Write-Host "  [OK] LimitBlankPasswordUse=0 (blank password remote access diizinkan)" -ForegroundColor Gray
    } else {
        if (-not $AuditOnly) {
            Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name LimitBlankPasswordUse -Value 0
            $remoteShutdownReport.Actions += "LimitBlankPasswordUse diatur ke 0"
            Write-Host "  [FIX] LimitBlankPasswordUse -> 0" -ForegroundColor Yellow
        } else {
            Write-Host "  [AUDIT] LimitBlankPasswordUse=$blankPw (sebaiknya 0 agar remote akses tanpa password diizinkan)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  [SKIP] Gagal cek LimitBlankPasswordUse." -ForegroundColor DarkGray
}

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

$reportFile = Join-Path -Path $PSScriptRoot -ChildPath "WOL-Report-$($env:COMPUTERNAME)-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
$report | ConvertTo-Json -Depth 5 | Out-File -FilePath $reportFile -Encoding UTF8

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " Selesai. Laporan disimpan di:" -ForegroundColor Cyan
Write-Host " $reportFile" -ForegroundColor White
if ($AuditOnly) {
    Write-Host "`n Mode ini hanya AUDIT. Jalankan ulang TANPA -AuditOnly untuk memperbaiki otomatis." -ForegroundColor Yellow
} else {
    Write-Host "`n Setting WOL dan Remote Shutdown selesai diterapkan." -ForegroundColor Green
    Write-Host " Disarankan RESTART komputer ini agar seluruh perubahan berlaku penuh." -ForegroundColor Yellow
    Write-Host " Setelah restart, server dapat menjalankan: shutdown /s /m \\$($env:COMPUTERNAME) /t 10 /f" -ForegroundColor Cyan
}
Write-Host "==========================================================" -ForegroundColor Cyan

