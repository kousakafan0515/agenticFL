$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_local_b2_client_validation_20261014_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_local_b2_validation.sh'
$manifestPath = Join-Path $runRoot 'background_launch_manifest.json'
if (Test-Path -LiteralPath $manifestPath) { throw "Refusing to overwrite launch manifest" }
$records = @()
foreach ($client in @('A','B','C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $stdout = Join-Path $clientRoot 'background.stdout.log'
    $stderr = Join-Path $clientRoot 'background.stderr.log'
    $status = Join-Path $clientRoot 'background_status.json'
    if ((Test-Path $stdout) -or (Test-Path $stderr) -or (Test-Path $status) -or (Test-Path (Join-Path $clientRoot 'validation'))) { throw "Refusing to overwrite Client $client validation" }
    $p = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash',$scriptPath,$client) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$p.Id;stdout=$stdout;stderr=$stderr;status=$status}
}
$manifest = [ordered]@{schema_version='stage3_2.local_b2_validation_launch.v1';started_at=[DateTimeOffset]::Now.ToString('o');policy='three independent validations; no training, Teacher, aggregation, or B3';processes=$records}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6
