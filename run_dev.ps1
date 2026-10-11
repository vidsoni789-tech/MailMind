# PersonalMail AI — Local Development Startup Script (PowerShell)
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   PersonalMail AI — Multi-Agent Assistant OS   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Check Python virtual environment
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[!] Python virtual environment not found in .\.venv" -ForegroundColor Red
    Write-Host "    Please run: python -m venv .venv && .\.venv\Scripts\pip install -e ." -ForegroundColor Yellow
    exit 1
}

# 2. Check environment file
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 3. Check frontend dependencies
if (-not (Test-Path ".\frontend\node_modules")) {
    Write-Host "[*] Installing frontend dependencies in ./frontend..." -ForegroundColor Yellow
    Push-Location ".\frontend"
    npm install
    Pop-Location
}

# 4. Start FastAPI backend server in background job
Write-Host "[+] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn langmail.api.app:app --host 127.0.0.1 --port 8000" -PassThru

# 5. Start Vite frontend server
Write-Host "[+] Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
Write-Host "    Press CTRL+C to terminate both servers." -ForegroundColor DarkGray

Push-Location ".\frontend"
try {
    npm run dev
} finally {
    Write-Host "`nStopping backend server (PID: $($backendProcess.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    Pop-Location
    Write-Host "[OK] Shutdown complete." -ForegroundColor Green
}
