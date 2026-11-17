# bioSSbD-py: create the environment, install, run the tests and build the example dossier.
# Run from the repository folder in a normal (non-Administrator) PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\setup_and_test.ps1
# Output is saved to test_report.txt so it can be reviewed afterwards.

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$report = Join-Path $PSScriptRoot "test_report.txt"
Start-Transcript -Path $report -Force | Out-Null

Write-Host "== Python"
$py = $null
foreach ($v in @("3.12", "3.13")) {
    & py "-$v" --version 2>$null
    if ($LASTEXITCODE -eq 0) { $py = "-$v"; break }
}
if (-not $py) {
    Write-Host "Python 3.12/3.13 not found for this user. Install it with:"
    Write-Host "  winget install -e --id Python.Python.3.12"
    Stop-Transcript | Out-Null
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "== Creating virtual environment (.venv)"
    & py $py -m venv .venv
}
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "== Installing bioSSbD-py with QSDsan, Brightway, GUI, tests and notebooks"
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -e ".[dev,notebooks,gui,qsdsan,brightway,openlca]"

Write-Host "== Versions"
& $python -c "import biossbd, qsdsan, biosteam, bw2data, streamlit, olca_ipc; print('biossbd', biossbd.__version__, '| qsdsan', qsdsan.__version__, '| biosteam', biosteam.__version__, '| bw2data', bw2data.__version__, '| streamlit', streamlit.__version__)"

Write-Host "== Tool status"
& $python -c "from biossbd import registry; print(registry.status_table()[['tool','licence','status']].to_string(index=False))"

Write-Host "== Tests (including live PubChem and Our World in Data checks)"
$env:BIOSSBD_ONLINE = "1"
& $python -m pytest -v -rs

Write-Host "== Example dossier"
& (Join-Path $PSScriptRoot ".venv\Scripts\biossbd.exe") dossier examples\acod\acod_system.yaml -o acod_dossier.md

Stop-Transcript | Out-Null
Write-Host "Done. Report: $report"
