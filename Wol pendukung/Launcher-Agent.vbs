' Launcher-Agent.vbs
Dim shell, psScript
psScript = "C:\\laragon\\www\\MaskomApp\\Wol pendukung\\Agent-Monitor.ps1"
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & psScript & """ -ServerUrl """ & "http://192.168.18.146:3000" & """", 0, False