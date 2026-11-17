# Open the bioSSbD-py graphical interface in your browser.
# Run from the repository folder:  powershell -ExecutionPolicy Bypass -File .\start_gui.ps1
# Stop it with Ctrl+C in this window.
Set-Location -Path $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Run setup_and_test.ps1 first."
    exit 1
}
& $python -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing the GUI dependencies (Streamlit)..."
    & $python -m pip install -e ".[gui]"
}
& $python -m biossbd.cli gui
