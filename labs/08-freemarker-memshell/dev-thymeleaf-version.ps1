# dev-thymeleaf-version.ps1 - swap the thymeleaf jars inside the running container's
# fat jar to a chosen version, then restart. Dev loop only.
param(
  [string]$ThymeleafVersion = "3.0.11.RELEASE",
  [string]$Container = "freemarker-memshell",
  [string]$JdkHome = "C:\Program Files\Java\jdk1.8.0_151",
  [string]$Port = "8098"
)
$ErrorActionPreference = "Stop"
$jarExe = Join-Path $JdkHome "bin\jar.exe"
$work = Join-Path $env:TEMP "lab08-thymeleaf"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null

Write-Host "[1/3] pull fat jar out of the container"
docker cp "${Container}:/app/app.jar" "$work\app.jar" | Out-Null
Push-Location $work
& $jarExe xf "$work\app.jar"
Pop-Location

Write-Host "[2/3] download thymeleaf $ThymeleafVersion jars"
$jars = @(
  @{ path = "org/thymeleaf/thymeleaf"; file = "thymeleaf-$ThymeleafVersion.jar" },
  @{ path = "org/thymeleaf/thymeleaf-spring5"; file = "thymeleaf-spring5-$ThymeleafVersion.jar" }
)
foreach ($j in $jars) {
  $url = "https://repo1.maven.org/maven2/$($j.path)/$ThymeleafVersion/$($j.file)"
  $dest = Join-Path $work "newjars\$($j.file)"
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Write-Host "    $url"
  Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}

# copy into BOOT-INF/lib under the original (version-less target) names
$libDir = Join-Path $work "BOOT-INF\lib"
Get-ChildItem $libDir -Filter "thymeleaf-3.0.15.RELEASE.jar" | Remove-Item -Force
Get-ChildItem $libDir -Filter "thymeleaf-spring5-3.0.15.RELEASE.jar" | Remove-Item -Force
Copy-Item (Join-Path $work "newjars\thymeleaf-$ThymeleafVersion.jar") (Join-Path $libDir "thymeleaf-$ThymeleafVersion.jar")
Copy-Item (Join-Path $work "newjars\thymeleaf-spring5-$ThymeleafVersion.jar") (Join-Path $libDir "thymeleaf-spring5-$ThymeleafVersion.jar")
Get-ChildItem $libDir -Filter "thymeleaf*.jar" | Select-Object -ExpandProperty Name

Write-Host "[3/3] repack + push + restart"
Push-Location $work
& $jarExe uf "$work\app.jar" "BOOT-INF/lib"
Pop-Location
docker cp "$work\app.jar" "${Container}:/app/app.jar" | Out-Null
docker restart $Container | Out-Null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 2
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/healthz" -UseBasicParsing -TimeoutSec 4
    if ($r.Content -eq 'ok') { Write-Host "[+] healthy"; exit 0 }
  } catch {}
}
Write-Host "[!] not healthy"
exit 1
