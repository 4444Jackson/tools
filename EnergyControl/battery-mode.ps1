# Battery mode switch for LENOVO 81Y2 (ZhaoYang K4e-IIL)
# Writes the charge mode directly to the EC via \\.\EnergyDrv.
# No Vantage, no service, no startup task. The setting persists in firmware.
# ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.

$tool = Join-Path $PSScriptRoot 'EnergyControl.exe'
if (-not (Test-Path $tool)) {
    Write-Host "EnergyControl.exe not found next to this script." -ForegroundColor Red
    exit 1
}

function Show-Status {
    $raw = & $tool charge direct get 2>&1 | Out-String
    try { $s = $raw | ConvertFrom-Json } catch { Write-Host $raw; return }
    Write-Host ""
    Write-Host "  Mode      : $($s.mode)" -ForegroundColor Cyan
    Write-Host "  Storage   : $($s.storageEnabled)   Quick: $($s.quickEnabled)"
    Write-Host "  Backend   : $($s.backend)  ($($s.protocol))"
    Write-Host ""
}

Write-Host "=== Lenovo battery charge mode (81Y2) ==="
Show-Status
Write-Host "  [1] Storage  - battery care, firmware preset cap (~55-60%), always-plugged"
Write-Host "  [2] Normal   - standard full charge (before travel)"
Write-Host "  [3] Express  - quick charge"
Write-Host "  [4] Status only (read, no write)"
Write-Host "  [Q] Quit"
Write-Host ""
$choice = Read-Host "Select"

switch ($choice) {
    '1' { $mode = 'storage' }
    '2' { $mode = 'normal' }
    '3' { $mode = 'express' }
    '4' { Show-Status; exit 0 }
    default { Write-Host "No change made."; exit 0 }
}

& $tool charge direct set $mode --apply
Write-Host ""
Write-Host "--- after ---"
Show-Status
