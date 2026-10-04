# Crea dist\Dettato-Setup.exe: ambiente Python, Dettato.exe (PyInstaller), installer (Inno Setup).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creo l'ambiente Python (.venv)..."
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3 non trovato: installalo da https://www.python.org/downloads/windows/" }
}

Write-Host "Installo le dipendenze..."
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt pyinstaller --quiet
if ($LASTEXITCODE -ne 0) { throw "Installazione delle dipendenze non riuscita" }

Write-Host "Eseguo i test..."
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Test falliti: build interrotta" }

$version = (& $python -c "import dettato; print(dettato.__version__)").Trim()
Write-Host "Versione $version"
$v = ($version.Split(".") + @("0", "0", "0"))[0..3] -join ", "
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($v), prodvers=($v)),
  kids=[
    StringFileInfo([
      StringTable('041004B0', [
        StringStruct('FileDescription', 'Dettato'),
        StringStruct('ProductName', 'Dettato'),
        StringStruct('FileVersion', '$version'),
        StringStruct('ProductVersion', '$version'),
        StringStruct('OriginalFilename', 'Dettato.exe'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0410, 1200])])
  ]
)
"@ | ForEach-Object { [IO.File]::WriteAllText((Join-Path $PSScriptRoot "version_info.txt"), $_, (New-Object Text.UTF8Encoding $false)) }

Write-Host "Creo Dettato.exe..."
& $python scripts\make_icon.py
& $python -m PyInstaller --noconfirm --clean dettato.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller non riuscito" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Inno Setup non trovato, lo installo con winget..."
    winget install --id JRSoftware.InnoSetup -e --scope user --silent --accept-package-agreements --accept-source-agreements
    $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
}

Write-Host "Creo l'installer..."
& $iscc /Qp "/DAppVersion=$version" installer\dettato.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup non riuscito" }

Write-Host ""
Write-Host "Fatto: dist\Dettato-Setup.exe"
