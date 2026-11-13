# =============================================================================
# build-memshell.ps1
#   1) 用 JDK8 编译"被注入物" MemshellFilter.java（只依赖 servlet-api）
#   2) base64 编码 -> src/main/resources/memshell/MemshellFilter.class.b64
#   3) 把 base64 回填到 InjectHelper.java 的 @@MEMSHELL_B64@@ 占位符
#
# 重新出题 / 改 payload 后跑一次即可。用法：
#   pwsh -File .\build-memshell.ps1
# =============================================================================
[CmdletBinding()]
param(
    [string]$JdkHome = "C:\Program Files\Java\jdk1.8.0_151",
    [string]$ServletApiJar = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pluginDir = Join-Path $root "memshell-plugin"
$outDir = Join-Path $env:TEMP "memshell-classes"
$resDir = Join-Path $root "src\main\resources\memshell"

$javac = Join-Path $JdkHome "bin\javac.exe"
$javap = Join-Path $JdkHome "bin\javap.exe"
if (-not (Test-Path $javac)) { throw "javac not found: $javac" }

# --- 1. servlet-api.jar ---
if (-not $ServletApiJar) {
    $ServletApiJar = Join-Path $env:TEMP "javax.servlet-api-4.0.1.jar"
}
if (-not (Test-Path $ServletApiJar)) {
    $url = "https://repo1.maven.org/maven2/javax/servlet/javax.servlet-api/4.0.1/javax.servlet-api-4.0.1.jar"
    Write-Host "[*] downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $ServletApiJar -UseBasicParsing
}
Write-Host "[*] servlet-api: $ServletApiJar"

# --- 2. compile ---
if (Test-Path $outDir) { Remove-Item -Recurse -Force $outDir }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$src = Join-Path $pluginDir "com\lab\themepreview\memshell\plugin\MemshellFilter.java"
Write-Host "[*] compiling MemshellFilter.java (target 1.8)"
& $javac -encoding UTF-8 -source 1.8 -target 1.8 -nowarn -cp $ServletApiJar -d $outDir $src
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

$classFile = Join-Path $outDir "com\lab\themepreview\memshell\plugin\MemshellFilter.class"
if (-not (Test-Path $classFile)) { throw "class file not produced: $classFile" }

Write-Host "[*] bytecode version check:"
& $javap -verbose -cp $outDir com.lab.themepreview.memshell.plugin.MemshellFilter |
    Select-String -Pattern "major version|minor version" | ForEach-Object { Write-Host "    $_" }

# --- 3. base64 -> resource ---
New-Item -ItemType Directory -Force -Path $resDir | Out-Null
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($classFile))
[IO.File]::WriteAllText((Join-Path $resDir "MemshellFilter.class.b64"), $b64, (New-Object Text.UTF8Encoding($false)))
Write-Host "[*] wrote $resDir\MemshellFilter.class.b64 ($($b64.Length) chars)"

# --- 4. inject into InjectHelper.java ---
$helper = Join-Path $root "src\main\java\com\lab\themepreview\memshell\InjectHelper.java"
$text = [IO.File]::ReadAllText($helper)
$pattern = 'public static final String MEMSHELL_CLASS_B64 = "[^"]*";'
if ($text -notmatch $pattern) { throw "placeholder not found in InjectHelper.java" }
$new = 'public static final String MEMSHELL_CLASS_B64 = "' + $b64 + '";'
$text = [Text.RegularExpressions.Regex]::Replace($text, $pattern, $new, 1)
[IO.File]::WriteAllText($helper, $text, (New-Object Text.UTF8Encoding($false)))
Write-Host "[*] InjectHelper.java updated"
Write-Host "[+] done"
