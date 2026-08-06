# Create a small GCP VM for the GitHub Actions self-hosted runner.
# Run from PowerShell (requires gcloud CLI + billing enabled).
#
#   cd scripts
#   .\create-gcp-runner-vm.ps1
#
# Then SSH in and run setup-gcp-actions-runner.sh with a GitHub registration token.

$ErrorActionPreference = "Stop"

$Project = "wee1-inhibitor-database"
$Zone = "us-east1-b"   # us-central1-* was exhausted; change if you recreate the VM
$Instance = "github-actions-runner"
$MachineType = "e2-small"   # 2 vCPU, 2 GB — enough for npm ci + vite build

Write-Host "Creating VM '$Instance' in project '$Project' (zone $Zone)..." -ForegroundColor Cyan

gcloud compute instances create $Instance `
  --project=$Project `
  --zone=$Zone `
  --machine-type=$MachineType `
  --image-family=ubuntu-2204-lts `
  --image-project=ubuntu-os-cloud `
  --boot-disk-size=20GB `
  --boot-disk-type=pd-standard `
  --tags=github-actions-runner

Write-Host ""
Write-Host "VM created. Next steps:" -ForegroundColor Green
Write-Host "  1. GitHub → Omri-Shavit/aprea → Settings → Actions → Runners → New self-hosted runner → Linux"
Write-Host "     Copy the registration token (valid ~1 hour)."
Write-Host ""
Write-Host "  2. SSH into the VM:"
Write-Host "     gcloud compute ssh $Instance --zone=$Zone --project=$Project"
Write-Host ""
Write-Host "  3. On the VM, run the setup script (after pushing scripts/ to main):"
Write-Host "     curl -fsSL https://raw.githubusercontent.com/Omri-Shavit/aprea/main/scripts/setup-gcp-actions-runner.sh -o setup.sh"
Write-Host "     chmod +x setup.sh"
Write-Host "     sudo ./setup.sh YOUR_REGISTRATION_TOKEN"
Write-Host ""
Write-Host "  4. Re-run the deploy workflow on GitHub (Actions → Deploy frontend → Run workflow)."
