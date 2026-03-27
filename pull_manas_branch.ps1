# Script to download Manas branch from GitHub
$repo = "Jinay-paleja/Traffix"
$branch = "Manas"
$tempDir = "$env:TEMP\Traffix-Manas"
$projectDir = Get-Location

Write-Host "Downloading Manas branch from GitHub..." -ForegroundColor Cyan

# Create temp directory
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Download ZIP
$zipUrl = "https://github.com/$repo/archive/refs/heads/$branch.zip"
$zipFile = "$tempDir\Manas.zip"

Write-Host "Downloading: $zipUrl" -ForegroundColor Yellow
Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
Write-Host "✓ Downloaded" -ForegroundColor Green

# Extract
Write-Host "Extracting files..." -ForegroundColor Yellow
Expand-Archive -Path $zipFile -DestinationPath $tempDir -Force
Write-Host "✓ Extracted" -ForegroundColor Green

# Find folder
$extractedFolder = Get-ChildItem -Path $tempDir -Directory | Where-Object { $_.Name -like "*Traffix*" }

if (-not $extractedFolder) {
    Write-Host "✗ Could not find extracted folder" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found: $($extractedFolder.Name)" -ForegroundColor Green

# Backup
$backupDir = "$projectDir\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Write-Host "Creating backup..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item -Path "$projectDir\*" -Destination $backupDir -Recurse -Force -Exclude "backup_*", ".git", "__pycache__", "venv"
Write-Host "✓ Backup created: $backupDir" -ForegroundColor Green

# Copy files
Write-Host "Copying files..." -ForegroundColor Yellow
$items = Get-ChildItem -Path $extractedFolder.FullName
foreach ($item in $items) {
    if ($item.Name -ne ".git") {
        Copy-Item -Path $item.FullName -Destination "$projectDir\$($item.Name)" -Recurse -Force
        Write-Host "  ✓ $($item.Name)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "✓ Successfully pulled Manas branch!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  pip install -r requirements.txt"
Write-Host "  python app.py"
Write-Host ""

# Cleanup
Remove-Item $tempDir -Recurse -Force
