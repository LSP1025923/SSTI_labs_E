# =============================================================================
# dev-fastboot.ps1 - dev-only speedup: compile changed classes on the host,
# repack the fat jar on the host, docker cp it in, restart the container.
# Production builds still use "docker build" (multi-stage Dockerfile).
#
# Usage:
#   & .\dev-fastboot.ps1
#   & .\dev-fastboot.ps1 -Files src\main\java\com\lab\themepreview\web\DiagController.java
# =============================================================================
param(
  [string[]]$Files = @(
    "src\main\java\com\lab\themepreview\memshell\InjectHelper.java"
  ),
  [string]$Container = "freemarker-memshell",
  [string]$JdkHome = "C:\Program Files\Java\jdk1.8.0_151",
  [string]$Port = "8098"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$javac = Join-Path $JdkHome "bin\javac.exe"
$jarExe = Join-Path $JdkHome "bin\jar.exe"
$work = Join-Path $env:TEMP "lab08-fastboot"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null

Write-Host "[1/4] copy fat jar out of container"
docker cp "${Container}:/app/app.jar" "$work\app.jar" | Out-Null
Push-Location $work
& $jarExe xf "$work\app.jar"
Pop-Location

# Windows argv splits a -cp containing ';', so flatten classes + libs and use a wildcard
$cpDir = Join-Path $work "cp"
New-Item -ItemType Directory -Force -Path $cpDir | Out-Null
Copy-Item -Recurse -Force "$work\BOOT-INF\classes\*" $cpDir
Copy-Item -Force "$work\BOOT-INF\lib\*.jar" $cpDir
$cpFlat = "$cpDir\*"

Write-Host "[2/4] compile"
$outDir = Join-Path $work "classes-out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$srcList = @($Files | ForEach-Object { Join-Path $root $_ })
& $javac -encoding UTF-8 -nowarn -cp $cpFlat -d $outDir @srcList
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

Write-Host "[3/4] repack app.jar on the host"
$updateDir = Join-Path $work "update"
New-Item -ItemType Directory -Force -Path $updateDir | Out-Null
foreach ($f in $Files) {
  $cls = [IO.Path]::GetFileNameWithoutExtension($f) + ".class"
  $found = Get-ChildItem -Recurse -File $outDir -Filter $cls | Select-Object -First 1
  if (-not $found) { throw "compiled class missing: $cls" }
  $rel = $found.FullName.Substring($outDir.Length + 1)
  $dest = Join-Path $updateDir ("BOOT-INF/classes/" + $rel)
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Copy-Item $found.FullName $dest
  Write-Host "    staged BOOT-INF/classes/$rel"
}
Push-Location $updateDir
& $jarExe uf "$work\app.jar" (Get-ChildItem -Recurse -File $updateDir | ForEach-Object { $_.FullName.Substring($updateDir.Length + 1) })
Pop-Location

Write-Host "[4/4] push jar + restart container"
docker cp "$work\app.jar" "${Container}:/app/app.jar" | Out-Null
docker restart $Container | Out-Null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 2
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/healthz" -UseBasicParsing -TimeoutSec 4
    if ($r.Content -eq 'ok') { Write-Host "[+] healthy"; exit 0 }
  } catch {}
}
Write-Host "[!] healthz not ready: docker logs $Container"
exit 1
