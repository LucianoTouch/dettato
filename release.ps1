# Pubblica una nuova versione di Dettato su GitHub Releases.
#   .\release.ps1 -Version 1.2.0 -Notes "Cosa cambia in questa versione"
# Chi ha Dettato installato riceve la notifica entro un giorno (o subito con "Controlla ora").
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notes = ""
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Versione non valida: usa il formato 1.2.3" }

$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\gh.exe" }
& $gh auth status *> $null
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI non collegata: esegui 'gh auth login'" }

$repo = (& $gh repo view --json nameWithOwner -q .nameWithOwner).Trim()
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appRepo = (& $python -c "from dettato import updater; print(updater.REPO)").Trim()
if ($repo -ne $appRepo) { throw "dettato\updater.py ha REPO='$appRepo' ma il repository e' '$repo'" }

if (& git status --porcelain) { throw "Ci sono modifiche non salvate in git: fai prima un commit" }
& git rev-parse -q --verify "refs/tags/v$Version" *> $null
if ($LASTEXITCODE -eq 0) { throw "La versione v$Version esiste gia'" }

# 1. Versione
$init = Join-Path $PSScriptRoot "dettato\__init__.py"
[IO.File]::WriteAllText($init, "__version__ = `"$Version`"`n", (New-Object Text.UTF8Encoding $false))

# 2. Build completa (test inclusi)
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { & git checkout -- $init; throw "Build non riuscita" }

# 3. Pacchetto leggero + manifest
$dist = Join-Path $PSScriptRoot "dist"
$setup = Join-Path $dist "Dettato-Setup.exe"
$zip = Join-Path $dist "Dettato-update.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $dist "Dettato\Dettato.exe") -DestinationPath $zip
$runtimeId = (Get-Content (Join-Path $PSScriptRoot "build\dettato\runtime_id.txt") -Raw).Trim()

function Describe($path) {
    [ordered]@{
        name   = (Split-Path $path -Leaf)
        sha256 = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
        size   = (Get-Item $path).Length
    }
}
$manifest = [ordered]@{
    version    = $Version
    runtime_id = $runtimeId
    notes      = $Notes
    setup      = Describe $setup
    update     = Describe $zip
}
$manifestPath = Join-Path $dist "manifest.json"
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))

# 4. Commit, tag, pubblicazione
& git add $init
& git commit -m "release: v$Version"
& git tag "v$Version"
& git push origin HEAD --tags
if ($LASTEXITCODE -ne 0) { throw "git push non riuscito" }

$body = @"
$Notes

## Installazione
1. Scarica **Dettato-Setup.exe** qui sotto ed eseguilo (non servono permessi di amministratore).
2. Se Windows mostra "Windows ha protetto il PC": clic su **Ulteriori informazioni** e poi **Esegui comunque** (il programma non e' firmato digitalmente).
3. Al primo avvio Dettato scarica il modello di trascrizione (1,5-3 GB): serve solo la prima volta.

Chi ha gia' Dettato installato riceve l'aggiornamento da solo.
"@
$notesFile = Join-Path $env:TEMP "dettato-release-notes.md"
[IO.File]::WriteAllText($notesFile, $body, (New-Object Text.UTF8Encoding $false))
& $gh release create "v$Version" $setup $zip $manifestPath --title "Dettato $Version" --notes-file $notesFile
if ($LASTEXITCODE -ne 0) { throw "Creazione della release non riuscita" }

# La cartella dell'exe (2+ GB) non serve piu': e' dentro il Setup.
Remove-Item -Recurse -Force (Join-Path $dist "Dettato")

Write-Host ""
Write-Host "Pubblicata Dettato $Version (aggiornamento $(if ($runtimeId) { 'runtime ' + $runtimeId }))."
Write-Host "Link per gli amici: https://github.com/$repo/releases/latest/download/Dettato-Setup.exe"
