# Deploy PM-Again — Frontend to Cloudflare Pages + Backend to Fly.io
# Usage: .\deploy-pm-again.ps1

param(
    [switch]$FrontendOnly,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

# PM-Again lives in a separate folder
$root = "d:\git\PM-Again"
if (-not (Test-Path $root)) {
    Write-Error "PM-Again not found at d:\git\PM-Again"
    exit 1
}

Write-Host "🚀 Deploying PM-Again..." -ForegroundColor Blue

# ─── Frontend ───
if (-not $BackendOnly) {
    Write-Host "`n📦 Building frontend..." -ForegroundColor Cyan
    Push-Location "$root\frontend"
    
    $env:VITE_API_BASE_URL = "https://pmo-platform-backend.fly.dev"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    
    Write-Host "🌎 Deploying to Cloudflare Pages..." -ForegroundColor Cyan
    npx wrangler pages deploy dist --project-name=pm-again --branch=main
    if ($LASTEXITCODE -ne 0) { throw "Pages deploy failed" }
    
    Pop-Location
    Write-Host "✅ Frontend deployed! https://main.pm-again.pages.dev" -ForegroundColor Green
}

# ─── Backend ───
if (-not $FrontendOnly) {
    Write-Host "`n🚀 Deploying backend to Fly.io..." -ForegroundColor Cyan
    Push-Location "$root\backend"
    
    fly deploy
    if ($LASTEXITCODE -ne 0) { throw "Backend deploy failed" }
    
    Pop-Location
    Write-Host "✅ Backend deployed! https://pmo-platform-backend.fly.dev" -ForegroundColor Green
}

Write-Host "`n🎉 PM-Again deploy complete!" -ForegroundColor Blue
