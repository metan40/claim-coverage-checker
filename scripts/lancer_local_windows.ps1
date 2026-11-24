# Auteur : Thierry MBARGA
# Lance claim-coverage-checker en local sous Windows, sans Docker, avec les
# mêmes réglages que le Space : modèle llama3.2:3b exécuté par Ollama.
# Prérequis : Python 3.10 ou plus récent, Ollama pour Windows installé et lancé.
# Usage, dans PowerShell, depuis le dossier du dépôt :
#     powershell -ExecutionPolicy Bypass -File scripts\lancer_local_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "1/4 Verification d'Ollama..."
try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null }
catch { Write-Host "Ollama ne repond pas : lancez l'application Ollama, puis relancez ce script."; exit 1 }

Write-Host "2/4 Modele de langage llama3.2:3b (telecharge une seule fois, 2,0 Go)..."
ollama pull llama3.2:3b

Write-Host "3/4 Environnement Python (.venv) et dependances..."
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-app.txt

Write-Host "4/4 Demarrage sur http://localhost:7860 (prete quand /ready repond 'ready')..."
$env:OLLAMA_MODEL = "llama3.2:3b"
$env:OLLAMA_TIMEOUT_SECONDS = "400"
& .\.venv\Scripts\python.exe -m uvicorn src.app:app --host 127.0.0.1 --port 7860
