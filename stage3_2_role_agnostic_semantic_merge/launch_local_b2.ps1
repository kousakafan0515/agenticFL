$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global1_to_local_b2_20261014_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_client_to_b2_with_secrets.sh'
if (Test-Path -LiteralPath $runRoot) { throw "Refusing to overwrite run root: $runRoot" }
New-Item -ItemType Directory -Path $runRoot | Out-Null
$records = @()
foreach ($client in @('A','B','C')) {
    $stdout = Join-Path $runRoot "client_${client}.stdout.log"
    $stderr = Join-Path $runRoot "client_${client}.stderr.log"
    $process = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash',$scriptPath,$client) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$process.Id;stdout=$stdout;stderr=$stderr}
}
$manifest = [ordered]@{schema_version='stage3_2.local_b2_background_launch.v1';started_at=[DateTimeOffset]::Now.ToString('o');policy='independent clients; stop after B2; no automatic restart';processes=$records}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runRoot 'launch_manifest.json') -Encoding UTF8
$manifest | ConvertTo-Json -Depth 5
