# 一键起全部靶场：先确保前端镜像存在，再交给根 compose。
#
# 用法：
#   scripts\up-all.ps1              # 起 01–07
#   scripts\up-all.ps1 -WithJava    # 额外起 08
#   scripts\up-all.ps1 -Rebuild     # 重新构建镜像
param(
    [switch]$WithJava,
    [switch]$Rebuild
)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$frontendImage = if ($env:FRONTEND_IMAGE) { $env:FRONTEND_IMAGE } else { 'ssti-frontend:local' }

$profileArgs = @()
$composeArgs = @()
if ($WithJava) { $profileArgs += @('--profile', 'java') }
if ($Rebuild)  { $composeArgs += '--build' }

# 前端镜像是所有 Python 靶场构建时的前置依赖
docker image inspect $frontendImage *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] 未找到 $frontendImage，先构建它"
    & (Join-Path $PSScriptRoot 'build-frontend.ps1')
}

Write-Host "[*] docker compose $($profileArgs -join ' ') up -d $($composeArgs -join ' ')"
Push-Location $root
try {
    docker compose @profileArgs up -d @composeArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose up 失败" }

    Write-Host ""
    Write-Host "[+] 状态："
    docker compose @profileArgs ps
}
finally {
    Pop-Location
}

Write-Host @'

端口速查
  8091 01-jinja-waf-fenjing   8092 02-jinja-chain     8093 03-mako-chain
  8094 04-tornado-chain       8095 05-jinja-sandbox   8096 06-blind-ssti
  8097 07-flask-memshell      8098 08-freemarker-memshell（-WithJava）
  8099 09-bottle-chain

健康检查：python scripts\verify_labs.py
'@
