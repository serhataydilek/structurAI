param(
  [string]$EnvName = "nerfstudio",
  [string]$PythonVersion = "3.8",
  [string]$CondaExe = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
  Write-Host "`n==> $Message"
}

if (-not (Test-Path -LiteralPath $CondaExe)) {
  $found = Get-Command conda -ErrorAction SilentlyContinue
  if ($found) {
    $CondaExe = $found.Source
  } else {
    throw "Conda was not found. Install Miniconda first: winget install --id Anaconda.Miniconda3 --exact --silent --accept-package-agreements --accept-source-agreements"
  }
}

Write-Step "Using conda at $CondaExe"

$envList = & $CondaExe env list
if ($envList -notmatch "^\s*$EnvName\s+") {
  Write-Step "Creating conda environment $EnvName"
  & $CondaExe create --name $EnvName -y "python=$PythonVersion"
} else {
  Write-Step "Conda environment $EnvName already exists"
}

$prefix = (& $CondaExe run -n $EnvName python -c "import sys; print(sys.prefix)").Trim()
$python = Join-Path $prefix "python.exe"
$scripts = Join-Path $prefix "Scripts"
$nsTrain = Join-Path $scripts "ns-train.exe"
$nsExport = Join-Path $scripts "ns-export.exe"
$vs2022Vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

Write-Step "Upgrading pip"
& $python -m pip install --upgrade pip

Write-Step "Installing CUDA PyTorch 2.1.2 cu118"
& $python -m pip install torch==2.1.2+cu118 torchvision==0.16.2+cu118 --extra-index-url https://download.pytorch.org/whl/cu118

Write-Step "Installing CUDA 11.8 build packages"
& $CondaExe install -n $EnvName -y -c nvidia cuda-nvcc=11.8.89 cuda-cudart=11.8.89 cuda-cudart-dev=11.8.89 cuda-cccl=11.8.89
& $CondaExe remove -n $EnvName -y cuda-cccl_win-64 cuda-version 2>$null

Write-Step "Installing Nerfstudio and gsplat"
& $python -m pip install --no-cache-dir nerfstudio
& $python -m pip install --no-deps --force-reinstall --no-cache-dir gsplat==1.4.0
& $python -m pip install --force-reinstall torch==2.1.2+cu118 torchvision==0.16.2+cu118 --extra-index-url https://download.pytorch.org/whl/cu118

Write-Step "Installing Windows runtime compatibility packages"
& $CondaExe install -n $EnvName -y -c conda-forge m2w64-gcc-libs
& $python -m pip install --force-reinstall --no-cache-dir fpsample==0.3.3

Write-Step "Patching CUDA 11.8 CUB header for Windows small macro collision"
$cubHeader = Join-Path $prefix "include\cub\device\dispatch\dispatch_segmented_sort.cuh"
if (Test-Path -LiteralPath $cubHeader) {
  $backup = "$cubHeader.structura-backup"
  if (-not (Test-Path -LiteralPath $backup)) {
    Copy-Item -LiteralPath $cubHeader -Destination $backup
  }
  $content = Get-Content -LiteralPath $cubHeader -Raw
  $content = $content.Replace("typename SmallAgentWarpMergeSortT::TempStorage small[segments_per_small_block];", "typename SmallAgentWarpMergeSortT::TempStorage small_storage[segments_per_small_block];")
  $content = $content.Replace("SmallAgentWarpMergeSortT(temp_storage.small[sid_within_block])", "SmallAgentWarpMergeSortT(temp_storage.small_storage[sid_within_block])")
  Set-Content -LiteralPath $cubHeader -Value $content -Encoding ASCII
}

if (-not (Test-Path -LiteralPath $vs2022Vcvars)) {
  Write-Warning "VS 2022 Build Tools with C++ workload was not found at $vs2022Vcvars. Install it with: winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --silent --accept-package-agreements --accept-source-agreements"
}

Write-Step "Running smoke tests"
& $CondaExe run -n $EnvName python -c "import torch; print('cuda:', torch.cuda.is_available()); print('torch cuda:', torch.version.cuda); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
& $CondaExe run -n $EnvName python -c "import nerfstudio; import gsplat; import fpsample; print('nerfstudio, gsplat, and fpsample import ok')"
& $CondaExe run -n $EnvName nvcc --version
& $CondaExe run -n $EnvName ns-train --help | Select-Object -First 8
& $CondaExe run -n $EnvName ns-export --help | Select-Object -First 8

Write-Step "Setting user environment variables"
[Environment]::SetEnvironmentVariable("NERFSTUDIO_PYTHON", $python, "User")
[Environment]::SetEnvironmentVariable("NERFSTUDIO_NS_TRAIN", $nsTrain, "User")
[Environment]::SetEnvironmentVariable("NERFSTUDIO_NS_EXPORT", $nsExport, "User")

Write-Host "`nNERFSTUDIO_PYTHON=$python"
Write-Host "NERFSTUDIO_NS_TRAIN=$nsTrain"
Write-Host "NERFSTUDIO_NS_EXPORT=$nsExport"
Write-Host "`nRestart terminals or set these variables in the current shell before starting the Structura backend."
