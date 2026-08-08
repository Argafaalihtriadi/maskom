<#
 ==============================================================================
 Agent-Monitor.ps1
 Screen capture agent untuk Monitoring Dashboard MaskomApp.
 Berjalan di background tiap PC client, capture layar setiap 3 detik
 dan upload ke server sebagai JPEG.

 CARA PAKAI (WAJIB Administrator):
   powershell -ExecutionPolicy Bypass -File .\Agent-Monitor.ps1

 INSTALASI SEBAGAI TASK SCHEDULER (biar auto-start saat boot):
   powershell -ExecutionPolicy Bypass -File .\Agent-Monitor.ps1 -Install

 UNINSTALL:
   powershell -ExecutionPolicy Bypass -File .\Agent-Monitor.ps1 -Uninstall
 ==============================================================================
#>

param(
    [string]$ServerUrl = "http://192.168.18.15:3000", # Ganti dengan IP server yang bisa dijangkau PC client
    [switch]$Install,
    [switch]$Uninstall,
    [int]$Interval = 3
)

if ($Install) {
    $taskName = "MaskomApp-MonitorAgent"
    $scriptPath = $MyInvocation.MyCommand.Path
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
    Write-Host "[OK] Agent terinstall sebagai Scheduled Task (auto-start saat boot)." -ForegroundColor Green
    exit
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName "MaskomApp-MonitorAgent" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Agent dihapus." -ForegroundColor Green
    exit
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[ERROR] Harus dijalankan sebagai Administrator." -ForegroundColor Red
    exit 1
}

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$hostname = $env:COMPUTERNAME
Write-Host "[Agent] Memulai monitoring untuk $hostname -> $ServerUrl" -ForegroundColor Cyan

while ($true) {
    try {
        $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
        $graphics.Dispose()

        $ms = New-Object System.IO.MemoryStream
        $bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Jpeg)
        $bitmap.Dispose()
        $bytes = $ms.ToArray()
        $ms.Dispose()

        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add("Content-Type", "application/octet-stream")
        $webClient.UploadData("$ServerUrl/api/monitor/screenshot/$hostname", "POST", $bytes) | Out-Null
        $webClient.Dispose()
    } catch {
        # silent — biar ga spam error
    }
    Start-Sleep -Seconds $Interval
}
