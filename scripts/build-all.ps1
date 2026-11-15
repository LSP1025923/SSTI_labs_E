# 构建全部靶场镜像（先前端，再各靶场）。
#
# 用法：
#   scripts\build-all.ps1              # 构建 01–07（Python 系）
#   scripts\build-all.ps1 --with-java  # 额外构建 08（Java，首次很慢）
param(
    [switch]$WithJava
)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot

& (Join-Path $PSScriptRoot 'build-frontend.ps1')

function Build-Lab {
    param([string]$LabDir, [string]$Tag)
    Write-Host ""
    Write-Host "[*] 构建 $Tag（labs/$LabDir/Dockerfile）"
    docker build -f (Join-Path $root "labs/$LabDir/Dockerfile") -t "$Tag`:local" $root
    if ($LASTEXITCODE -ne 0) { throw "$Tag 构建失败" }
}

Build-Lab '01-jinja-waf-fenjing' 'ssti-jinja-waf-fenjing'
Build-Lab '02-jinja-chain'       'ssti-jinja-chain'
Build-Lab '03-mako-chain'        'ssti-mako-chain'
Build-Lab '04-tornado-chain'     'ssti-tornado-chain'
Build-Lab '05-jinja-sandbox'     'ssti-jinja-sandbox'
Build-Lab '06-blind-ssti'        'ssti-blind'
Build-Lab '07-flask-memshell'    'ssti-flask-memshell'
Build-Lab '09-bottle-chain'      'ssti-bottle-chain'

if ($WithJava) {
    Write-Host ""
    Write-Host "[*] 构建 08-freemarker-memshell（Maven 首次下载依赖，可能 5–15 分钟）"
    docker build -t 'ssti-freemarker-memshell:local' (Join-Path $root 'labs/08-freemarker-memshell')
    if ($LASTEXITCODE -ne 0) { throw "08 构建失败" }
}

Write-Host ""
Write-Host "[+] 完成。镜像列表："
docker images --format '{{.Repository}}:{{.Tag}}' | Select-String '^ssti-'
Write-Host ""
Write-Host "    启动：scripts\up-all.ps1     健康检查：python scripts\verify_labs.py"
