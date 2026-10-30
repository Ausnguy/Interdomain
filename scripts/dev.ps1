param(
    # Spark is only a prototype that prints to the console and uses 1-2 GB of
    # RAM, so it is off unless you ask for it: .\scripts\dev.ps1 -Spark
    [switch]$Spark
)

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvUvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

Write-Host "Starting Interdomain infrastructure..."

Set-Location $Root

$Services = @("postgres", "kafka")
if ($Spark) { $Services += "spark" }

docker compose up -d @Services

Write-Host "Waiting for infrastructure..."
Start-Sleep -Seconds 8

Write-Host "Starting RIPE producer..."
Start-Process powershell.exe -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$Root'; & '$VenvPython' scripts\run_producer.py"

Write-Host "Starting Kafka consumer..."
Start-Process powershell.exe -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$Root'; & '$VenvPython' scripts\run_consumer.py"

Write-Host "Starting maintenance (prefix counts, partitions, retention)..."
Start-Process powershell.exe -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$Root'; & '$VenvPython' scripts\run_maintenance.py"

Write-Host "Starting FastAPI..."
Start-Process powershell.exe -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$Root'; & '$VenvUvicorn' interdomain.api.main:app --app-dir src --reload --reload-dir src"

Write-Host "Starting React..."
Start-Process powershell.exe -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$Root\frontend'; npm run dev"

Write-Host ""
Write-Host "Interdomain started."
Write-Host "Dashboard: http://localhost:5173"
Write-Host "API Docs:  http://127.0.0.1:8000/docs"
Write-Host ""
if ($Spark) {
    Write-Host "Spark logs: docker compose logs -f spark"
}