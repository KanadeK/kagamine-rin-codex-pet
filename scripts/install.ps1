param(
  [string]$Source = "pet",
  [string]$CodexHome = "",
  [string]$Python = "python",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot
try {
  & $Python -m rin_pet validate $Source --strict
  if ($LASTEXITCODE -ne 0) {
    throw "Strict pet validation failed; installation was not attempted."
  }
  $arguments = @("-m", "rin_pet", "install", "--source", $Source)
  if ($CodexHome) {
    $arguments += @("--codex-home", $CodexHome)
  }
  if ($DryRun) {
    $arguments += "--dry-run"
  }
  & $Python @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Installation failed. Run: $Python -m rin_pet doctor --source $Source"
  }
} finally {
  Pop-Location
}
