# =============================================================================
# dev-fastboot.ps1 - dev-only speedup: compile one class on the host, replace it
# inside the running container's fat jar, restart the container.
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

Write-Host "[1/4] copy fat jar out of container (for classpath)"
docker cp "${Container}:/app/app.jar" "$work\app.jar" | Out-Null
Push-Location $work
& $jarExe xf "$work\app.jar" BOOT-INF/classes BOOT-INF/lib 2>$null
Pop-Location

$libs = (Get-ChildItem -Recurse -File "$work\BOOT-INF\lib" -Filter *.jar | ForEach-Object { $_.FullName }) -join ';'
$cpAll = "$work\BOOT-INF\classes;$libs"

# Windows argv 会把含 ';' 的 -cp 拆坏（javac 的 @argfile 也不稳），
# 所以把 classes 和所有依赖 jar 拍平到一个目录，用通配符 classpath。
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

Write-Host "[3/4] push classes into /app/app.jar"
foreach ($f in $Files) {
  $cls = [IO.Path]::GetFileNameWithoutExtension($f) + ".class"
  $found = Get-ChildItem -Recurse -File $outDir -Filter $cls | Select-Object -First 1
  if (-not $found) { throw "compiled class missing: $cls" }
  $rel = $found.FullName.Substring($outDir.Length + 1) -replace '\\', '/'
  $dest = Join-Path $work ("stage/" + $rel)
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Copy-Item $found.FullName $dest
  $containerDir = "/tmp/stage/" + (Split-Path $rel)
  docker exec $Container sh -c "rm -rf /tmp/stage && mkdir -p $containerDir" | Out-Null
  docker cp $dest "${Container}:/tmp/stage/$rel" | Out-Null
  docker exec $Container sh -c "cd /tmp && jar uf /app/app.jar stage/$rel" | Out-Null
  Write-Host "    updated $rel"
}

Write-Host "[4/4] restart container"
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
