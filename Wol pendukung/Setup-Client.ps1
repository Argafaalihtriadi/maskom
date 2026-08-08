<#
 ==============================================================================
 Setup-Client.ps1
 Script lengkap untuk menyiapkan PC client agar kompatibel penuh dengan
 MaskomApp Web Dashboard (WOL, Remote Shutdown, File Transfer, Monitoring).

 Fungsi:
   1. Wake-on-LAN (WOL) — Magic Packet, EEE dimatikan
   2. Remote Shutdown — SMB firewall, Remote UAC disable, Remote Registry
   3. Remote Access — LimitBlankPasswordUse=0, Administrator aktif
   4. File Transfer — Buat C:\share, buka akses WMI
   5. Monitoring Agent — Install screen capture agent (Scheduled Task)
   6. Fast Startup — Dimatikan (biar WOL stabil)

 CARA PAKAI (WAJIB Administrator):
   # Audit saja (tidak mengubah apa pun)
   powershell -ExecutionPolicy Bypass -File .\Setup-Client.ps1 -AuditOnly

   # Setup lengkap + install monitoring agent
   powershell -ExecutionPolicy Bypass -File .\Setup-Client.ps1

   # Setup tanpa install monitoring agent
   powershell -ExecutionPolicy Bypass -File .\Setup-Client.ps1 -SkipAgent

 CARA UNINSTALL AGENT:
   powershell -ExecutionPolicy Bypass -File .\Agent-Monitor.ps1 -Uninstall
 ==============================================================================
#>

param(
    [switch]$AuditOnly,
    [switch]$SkipAgent,
    [string]$ServerUrl = "http://192.168.18.146:3000"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$report = [ordered]@{
    Hostname       = $env:COMPUTERNAME
    Timestamp      = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Mode           = if ($AuditOnly) { "AuditOnly" } else { "AuditAndFix" }
    Adapters       = @()
    RemoteShutdown = $null
    FastStartup    = $null
    ShareFolder    = $null
    WMI            = $null
    AdminAccount   = $null
    AgentInstalled = $null
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Step {
    param([string]$Label, [string]$Status, [string]$Detail = "")
    $icons = @{ OK = "[OK]"; FIX = "[FIX]"; WARN = "[WARN]"; SKIP = "[SKIP]"; INFO = "[INFO]"; ERROR = "[ERROR]" }
    $colors = @{ OK = "Gray"; FIX = "Yellow"; WARN = "DarkYellow"; SKIP = "DarkGray"; INFO = "DarkGray"; ERROR = "Red" }
    if ($icons.ContainsKey($Status)) { $icon = $icons[$Status] } else { $icon = "[$Status]" }
    if ($colors.ContainsKey($Status)) { $color = $colors[$Status] } else { $color = "White" }
    Write-Host " $icon $Label $Detail" -ForegroundColor $color
    if ($Detail) { Write-Host "       $Detail" -ForegroundColor DarkGray }
}

if (-not (Test-IsAdmin)) {
    Write-Host "[ERROR] Script ini HARUS dijalankan sebagai Administrator." -ForegroundColor Red
    Write-Host "Klik kanan PowerShell -> 'Run as Administrator', lalu jalankan ulang." -ForegroundColor Yellow
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " SETUP-CLIENT - Persiapan PC untuk MaskomApp" -ForegroundColor Cyan
Write-Host " Mode: $(if ($AuditOnly) {'AUDIT ONLY'} else {'AUDIT + AUTO FIX'})" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# =============================================================================
# 1. WOL - Network Adapter Settings
# =============================================================================
Write-Host "`n--- [1/6] Wake-on-LAN ---" -ForegroundColor Green

$adapters = Get-NetAdapter | Where-Object {
    $_.HardwareInterface -eq $true -and
    $_.Virtual -eq $false -and
    $_.InterfaceDescription -notmatch "Bluetooth|Virtual|Loopback|WAN Miniport"
}

if (-not $adapters) {
    Write-Step "Adapter fisik" "WARN" "Tidak ditemukan"
}

foreach ($adapter in $adapters) {
    $name = $adapter.Name
    $desc = $adapter.InterfaceDescription
    Write-Host "  Adapter: $name ($desc)" -ForegroundColor White

    $adapterReport = [ordered]@{ Name = $name; WakeOnMagicPacket = "?"; EnergyEfficientEth = "?"; DeviceWakeEnabled = "?"; Actions = @() }

    # Wake on Magic Packet
    try {
        $pm = Get-NetAdapterPowerManagement -Name $name -ErrorAction Stop
        if ($pm.WakeOnMagicPacket -ne "Enabled") {
            if (-not $AuditOnly) {
                Set-NetAdapterPowerManagement -Name $name -WakeOnMagicPacket Enabled -ErrorAction Stop
                $adapterReport.WakeOnMagicPacket = "Enabled (diperbaiki)"; $adapterReport.Actions += "WakeOnMagicPacket diaktifkan"
                Write-Step "  Wake on Magic Packet" "FIX"
            } else { Write-Step "  Wake on Magic Packet" "WARN" "DISABLED" }
        } else { Write-Step "  Wake on Magic Packet" "OK" }
    } catch { Write-Step "  Wake on Magic Packet" "SKIP" }

    # Energy Efficient Ethernet
    $advProps = Get-NetAdapterAdvancedProperty -Name $name -ErrorAction SilentlyContinue
    $eeeNames = @("Energy Efficient Ethernet", "Green Ethernet", "Advanced EEE", "EEE")
    foreach ($prop in $advProps) {
        if ($eeeNames -contains $prop.DisplayName -and $prop.DisplayValue -notmatch "Disabled|Off") {
            $adapterReport.EnergyEfficientEth = $prop.DisplayValue
            if (-not $AuditOnly) {
                try {
                    Set-NetAdapterAdvancedProperty -Name $name -DisplayName $prop.DisplayName -DisplayValue "Disabled" -ErrorAction Stop
                    $adapterReport.Actions += "$($prop.DisplayName) dinonaktifkan"
                    Write-Step "  $($prop.DisplayName)" "FIX" "-> Disabled"
                } catch { Write-Step "  $($prop.DisplayName)" "WARN" "Gagal set manual" }
            } else { Write-Step "  $($prop.DisplayName)" "WARN" "Enabled" }
        } elseif ($eeeNames -contains $prop.DisplayName) {
            Write-Step "  $($prop.DisplayName)" "OK" "Disabled"
        }
    }

    # Wake source
    $wakeArmedList = (powercfg /devicequery wake_armed) -join "`n"
    if ($wakeArmedList -match [Regex]::Escape($desc)) {
        $adapterReport.DeviceWakeEnabled = $true
        Write-Step "  Wake source (powercfg)" "OK"
    } else {
        $adapterReport.DeviceWakeEnabled = $false
        if (-not $AuditOnly) {
            try {
                powercfg /deviceenablewake "$desc" | Out-Null
                $adapterReport.Actions += "Diizinkan sebagai wake source"
                Write-Step "  Wake source (powercfg)" "FIX"
            } catch { Write-Step "  Wake source (powercfg)" "WARN" "Gagal" }
        } else { Write-Step "  Wake source (powercfg)" "WARN" "Belum diizinkan" }
    }
    $report.Adapters += $adapterReport
}

# =============================================================================
# 2. Remote Shutdown Support
# =============================================================================
Write-Host "`n--- [2/6] Remote Shutdown ---" -ForegroundColor Green

$rsReport = [ordered]@{ FirewallSMB = "?"; RemoteUAC = "?"; RemoteRegistry = "?"; LimitBlankPassword = "?"; Actions = @() }

# 2a. Firewall SMB
try {
    $fwRules = Get-NetFirewallRule -DisplayGroup "File and Printer Sharing" -ErrorAction Stop
    $smbInRules = $fwRules | Where-Object { $_.Direction -eq "Inbound" -and $_.Enabled -eq $true }
    if ($smbInRules.Count -gt 0) {
        $rsReport.FirewallSMB = "Enabled"; Write-Step "  Firewall SMB-In" "OK"
    } else {
        if (-not $AuditOnly) {
            try {
                netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes | Out-Null
                $rsReport.Actions += "Firewall SMB-In diaktifkan"; $rsReport.FirewallSMB = "Enabled (diperbaiki)"
                Write-Step "  Firewall SMB-In" "FIX"
            } catch { Write-Step "  Firewall SMB-In" "WARN" "Gagal" }
        } else { Write-Step "  Firewall SMB-In" "WARN" "Disabled" }
    }
} catch { Write-Step "  Firewall SMB-In" "SKIP" }

# 2b. Remote UAC
$regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
try {
    $filterPolicy = (Get-ItemProperty -Path $regPath -Name LocalAccountTokenFilterPolicy -ErrorAction SilentlyContinue).LocalAccountTokenFilterPolicy
    if ($null -eq $filterPolicy -or $filterPolicy -ne 1) {
        if (-not $AuditOnly) {
            New-ItemProperty -Path $regPath -Name LocalAccountTokenFilterPolicy -PropertyType DWord -Value 1 -Force | Out-Null
            $rsReport.Actions += "LocalAccountTokenFilterPolicy=1"
            $rsReport.RemoteUAC = "Disabled (diperbaiki)"
            Write-Step "  Remote UAC (LocalAccountTokenFilterPolicy)" "FIX" "-> 1"
        } else { Write-Step "  Remote UAC" "WARN" "NotSet/0 (perlu 1)" }
    } else { Write-Step "  Remote UAC" "OK" "Disabled" }
} catch { Write-Step "  Remote UAC" "SKIP" }

# 2c. Remote Registry
try {
    $svc = Get-Service -Name RemoteRegistry -ErrorAction Stop
    if ($svc.StartType -ne [ServiceStartMode]::Automatic) {
        if (-not $AuditOnly) {
            Set-Service -Name RemoteRegistry -StartupType Automatic
            $rsReport.Actions += "Remote Registry startup -> Automatic"
            Write-Step "  Remote Registry startup" "FIX"
        } else { Write-Step "  Remote Registry startup" "WARN" "$($svc.StartType)" }
    }
    if ($svc.Status -ne [ServiceControllerStatus]::Running) {
        if (-not $AuditOnly) {
            Start-Service -Name RemoteRegistry
            $rsReport.Actions += "Remote Registry dijalankan"
            $rsReport.RemoteRegistry = "Running (diperbaiki)"
            Write-Step "  Remote Registry service" "FIX" "-> Running"
        } else { Write-Step "  Remote Registry service" "WARN" "$($svc.Status)" }
    } else { Write-Step "  Remote Registry service" "OK" }
} catch { Write-Step "  Remote Registry service" "SKIP" }

# 2d. LimitBlankPasswordUse
try {
    $blankPw = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name LimitBlankPasswordUse -ErrorAction SilentlyContinue).LimitBlankPasswordUse
    if ($blankPw -eq 0) {
        $rsReport.LimitBlankPassword = "0 (OK)"
        Write-Step "  LimitBlankPasswordUse" "OK" "=0"
    } else {
        if (-not $AuditOnly) {
            Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name LimitBlankPasswordUse -Value 0
            $rsReport.Actions += "LimitBlankPasswordUse diatur ke 0"
            $rsReport.LimitBlankPassword = "0 (diperbaiki)"
            Write-Step "  LimitBlankPasswordUse" "FIX" "-> 0"
        } else { Write-Step "  LimitBlankPasswordUse" "WARN" "=$blankPw (perlu 0)" }
    }
} catch { Write-Step "  LimitBlankPasswordUse" "SKIP" }

# 2e. Test SMB (port 445)
try {
    $testConn = Test-NetConnection -ComputerName $env:COMPUTERNAME -Port 445 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($testConn) { Write-Step "  Port 445 (SMB)" "OK" } else { Write-Step "  Port 445 (SMB)" "WARN" "Tidak terbuka" }
} catch { Write-Step "  Port 445 (SMB)" "SKIP" }

$report.RemoteShutdown = $rsReport

# =============================================================================
# 3. Enable Administrator Account
# =============================================================================
Write-Host "`n--- [3/6] Administrator Account ---" -ForegroundColor Green

try {
    $adminUser = Get-LocalUser -Name "Administrator" -ErrorAction Stop
    if (-not $adminUser.Enabled) {
        if (-not $AuditOnly) {
            Enable-LocalUser -Name "Administrator"
            $report.AdminAccount = "Enabled (diperbaiki)"
            Write-Step "  Administrator account" "FIX" "-> Enabled"
        } else { Write-Step "  Administrator account" "WARN" "Disabled" }
    } else { Write-Step "  Administrator account" "OK"; $report.AdminAccount = "Enabled" }
} catch {
    # Maybe English Windows has different name
    try {
        $adminUser = Get-LocalUser -Name "Admin" -ErrorAction Stop
        if (-not $adminUser.Enabled) {
            if (-not $AuditOnly) { Enable-LocalUser -Name "Admin"; $report.AdminAccount = "Enabled (diperbaiki)"; Write-Step "  Admin account" "FIX" }
            else { Write-Step "  Admin account" "WARN" "Disabled" }
        } else { Write-Step "  Admin account" "OK"; $report.AdminAccount = "Enabled" }
    } catch { Write-Step "  Administrator account" "SKIP" "Tidak ditemukan" }
}

# =============================================================================
# 4. File Transfer - C:\share folder
# =============================================================================
Write-Host "`n--- [4/6] File Transfer (C:\share) ---" -ForegroundColor Green

$sharePath = "C:\share"
if (-not (Test-Path $sharePath)) {
    if (-not $AuditOnly) {
        try {
            New-Item -Path $sharePath -ItemType Directory -Force | Out-Null
            $report.ShareFolder = "Created"
            Write-Step "  Folder $sharePath" "FIX" "-> Dibuat"
        } catch {
            $report.ShareFolder = "Gagal buat folder"
            Write-Step "  Folder $sharePath" "ERROR" $_.Exception.Message
        }
    } else { Write-Step "  Folder $sharePath" "WARN" "Belum ada" }
} else { Write-Step "  Folder $sharePath" "OK"; $report.ShareFolder = "Exists" }

# =============================================================================
# 5. WMI Firewall Rules
# =============================================================================
Write-Host "`n--- [5/6] WMI (Remote Management) ---" -ForegroundColor Green

$wmiRules = @(
    @{Name = "Windows Management Instrumentation (DCOM-In)"; Group = "Windows Management Instrumentation"}
    @{Name = "Windows Management Instrumentation (WMI-In)"; Group = "Windows Management Instrumentation"}
)

$wmiReport = @()
foreach ($rule in $wmiRules) {
    try {
        $fw = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
        if ($fw -and $fw.Enabled -eq $true) {
            $wmiReport += "$($rule.Name): OK"
            Write-Step "  $($rule.Name)" "OK"
        } else {
            if (-not $AuditOnly) {
                try {
                    netsh advfirewall firewall set rule name="$($rule.Name)" new enable=Yes | Out-Null
                    $wmiReport += "$($rule.Name): Enabled (diperbaiki)"
                    Write-Step "  $($rule.Name)" "FIX"
                } catch { Write-Step "  $($rule.Name)" "WARN" "Gagal enable" }
            } else { Write-Step "  $($rule.Name)" "WARN" "Disabled" }
        }
    } catch { Write-Step "  $($rule.Name)" "SKIP" }
}
$report.WMI = if ($wmiReport.Count -gt 0) { $wmiReport -join "; " } else { "No changes" }

# =============================================================================
# 6. Install Monitoring Agent (Scheduled Task)
# =============================================================================
if (-not $SkipAgent) {
    Write-Host "`n--- [6/6] Monitoring Agent ---" -ForegroundColor Green
    $agentScript = Join-Path -Path $scriptDir -ChildPath "Agent-Monitor.ps1"

    if (-not (Test-Path $agentScript)) {
        Write-Step "  Agent-Monitor.ps1" "ERROR" "Tidak ditemukan di $agentScript"
        $report.AgentInstalled = "Script not found"
    } else {
        if (-not $AuditOnly) {
            $taskName = "MaskomApp-MonitorAgent"
            $launcherVbs = Join-Path -Path $scriptDir -ChildPath "Launcher-Agent.vbs"
            try {
                # Generate Launcher-Agent.vbs
                $vbsContent = @"
' Launcher-Agent.vbs
Dim shell, psScript
psScript = "$($agentScript -replace '\\', '\\')"
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psScript & """ -ServerUrl """ & "$ServerUrl" & """", 0, False
"@
                [System.IO.File]::WriteAllText($launcherVbs, $vbsContent, [System.Text.Encoding]::UTF8)
                # Daftarkan Scheduled Task — trigger AtLogOn biar berjalan di sesi user (bisa akses layar)
                Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
                $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B //NoLogo `"$($launcherVbs)`""
                $trigger = New-ScheduledTaskTrigger -AtLogOn
                $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
                Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
                Write-Step "  Scheduled Task" "FIX" "Terinstall (auto-start saat login)"
                $report.AgentInstalled = "Installed"
                # Jalankan agent SEKARANG via WMI (Win32_Process.Create) — paling reliable
                $cmdLine = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$agentScript`" -ServerUrl `"$ServerUrl`""
                $result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmdLine }
                Start-Sleep -Seconds 2
                if ($result.ReturnValue -eq 0) {
                    Write-Step "  Agent" "OK" "Berjalan di background (PID: $($result.ProcessId))"
                } else {
                    Write-Step "  Agent" "WARN" "WMI gagal (kode: $($result.ReturnValue)), coba manual:"
                    Write-Step "  Agent" "INFO" "powershell -ExecutionPolicy Bypass -File `"$agentScript`" -ServerUrl `"$ServerUrl`""
                }
            } catch {
                Write-Step "  Agent" "ERROR" $_.Exception.Message
                $report.AgentInstalled = "Gagal: $($_.Exception.Message)"
            }
        } else {
            Write-Step "  Scheduled Task" "WARN" "Belum terinstall (AuditOnly)"
            $report.AgentInstalled = "Not installed (AuditOnly)"
        }
    }
} else {
    Write-Host "`n--- [6/6] Monitoring Agent ---" -ForegroundColor Green
    Write-Step "  Agent" "SKIP" "SkipAgent flag"
}

# =============================================================================
# Fast Startup (dimatikan)
# =============================================================================
Write-Host "`n--- Fast Startup Windows ---" -ForegroundColor Green
$powerKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power"
$hiberboot = (Get-ItemProperty -Path $powerKey -Name HiberbootEnabled -ErrorAction SilentlyContinue).HiberbootEnabled

if ($null -eq $hiberboot) {
    Write-Step "  Fast Startup" "INFO" "Tidak terdeteksi"
    $report.FastStartup = "Tidak terdeteksi"
} elseif ($hiberboot -eq 1) {
    if (-not $AuditOnly) {
        Set-ItemProperty -Path $powerKey -Name HiberbootEnabled -Value 0
        $report.FastStartup = "Disabled (diperbaiki)"
        Write-Step "  Fast Startup" "FIX" "-> Disabled"
    } else {
        Write-Step "  Fast Startup" "WARN" "Enabled (sebaiknya Disabled)"
        $report.FastStartup = "Enabled"
    }
} else {
    Write-Step "  Fast Startup" "OK" "Disabled"
    $report.FastStartup = "Disabled"
}

# =============================================================================
# Selesai
# =============================================================================
$reportFile = Join-Path -Path $scriptDir -ChildPath "SetupReport-$($env:COMPUTERNAME)-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
$report | ConvertTo-Json -Depth 5 | Out-File -FilePath $reportFile -Encoding UTF8

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " SELESAI. Laporan disimpan di:" -ForegroundColor Cyan
Write-Host " $reportFile" -ForegroundColor White
if ($AuditOnly) {
    Write-Host "`n Mode AUDIT. Jalankan ulang TANPA -AuditOnly untuk menerapkan perubahan." -ForegroundColor Yellow
} else {
    Write-Host "`n Semua pengaturan sudah diterapkan." -ForegroundColor Green
    Write-Host " Disarankan RESTART komputer agar perubahan maksimal." -ForegroundColor Yellow
    Write-Host " Setelah restart, server dapat mengontrol PC ini sepenuhnya." -ForegroundColor Cyan
}
Write-Host "==========================================================" -ForegroundColor Cyan
