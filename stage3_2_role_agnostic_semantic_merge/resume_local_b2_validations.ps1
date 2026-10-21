$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_local_b2_client_validation_20261014_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_local_b2_validation.sh'
$manifestPath = Join-Path $runRoot 'resume_launch_manifest_001.json'
if (Test-Path -LiteralPath $manifestPath) { throw "Refusing to overwrite resume manifest" }
$records = @()
foreach ($client in @('A','B','C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $statusPath = Join-Path $clientRoot 'background_status.json'
    $status = Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json
    if ($status.status -ne 'failed') { throw "Client $client is not failed: $($status.status)" }
    $stdout = Join-Path $clientRoot 'resume_001.stdout.log'
    $stderr = Join-Path $clientRoot 'resume_001.stderr.log'
    if ((Test-Path $stdout) -or (Test-Path $stderr)) { throw "Refusing to overwrite Client $client resume logs" }
    $p = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash',$scriptPath,$client,'resume') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$p.Id;stdout=$stdout;stderr=$stderr;status=$statusPath}
}
$manifest = [ordered]@{schema_version='stage3_2.local_b2_validation_resume.v1';started_at=[DateTimeOffset]::Now.ToString('o');policy='resume frozen prefixes in independent segments; no overwrite';processes=$records}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6
