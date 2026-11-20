# Сборка Windows: PyInstaller -> автономный hackmeskay.exe
# Запуск: powershell -ExecutionPolicy Bypass -File build\build_windows.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

py -m pip install -r requirements.txt
py -m PyInstaller `
  --noconfirm --clean --onefile --console `
  --name hackmeskay `
  --paths src `
  --add-data "data;data" `
  --hidden-import aiohttp `
  --hidden-import colorama `
  entrypoint.py

$dist = Join-Path $root 'dist'
# ВАЖНО: копируем только шаблон модов и пустые каталоги.
# Если папки уже есть — НЕ перезаписываем (сохранение данных игрока).
foreach ($dir in @('mods', 'saves', 'config')) {
    $target = Join-Path $dist $dir
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target | Out-Null
    }
}
$templateMod = Join-Path $root 'mods/example_mod'
$targetMod = Join-Path $dist 'mods/example_mod'
if (-not (Test-Path -LiteralPath $targetMod) -and (Test-Path -LiteralPath $templateMod)) {
    Copy-Item -LiteralPath $templateMod -Destination $targetMod -Recurse
}
Copy-Item -LiteralPath (Join-Path $root 'mods/mods.json') -Destination (Join-Path $dist 'mods/mods.json') -Force -ErrorAction SilentlyContinue

Write-Host "Готово: $dist\hackmeskay.exe"
