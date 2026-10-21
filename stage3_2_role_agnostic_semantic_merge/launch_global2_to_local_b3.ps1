$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global2_to_local_b3_20261015_r1'
$validationRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global2_client_validation_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_global2_to_local_b3_with_secrets.sh'
if (Test-Path -LiteralPath $runRoot) { throw "Refusing to overwrite run root: $runRoot" }
New-Item -ItemType Directory -Path $runRoot | Out-Null
$records = @()
foreach ($client in @('A','B','C')) {
    $summary = Join-Path $validationRoot "client_$client\validation\summary.json"
    if (-not (Test-Path -LiteralPath $summary)) { throw "Missing Global2 validation summary for Client $client" }
    $value = Get-Content -Raw -LiteralPath $summary | ConvertFrom-Json
    if ($value.status -ne 'complete' -or $value.task_count -ne 134 -or -not $value.api_clean) {
        throw "Client $client has not completed an API-clean Global2 validation"
    }
    $stdout = Join-Path $runRoot "client_$client.stdout.log"
    $stderr = Join-Path $runRoot "client_$client.stderr.log"
    $process = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash', $scriptPath, $client, 'fresh') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$process.Id;stdout=$stdout;stderr=$stderr;started_at=[DateTimeOffset]::Now.ToString('o')}
}
$manifest = [ordered]@{
    schema_version = 'stage3_2.global2_to_local_b3_background_launch.v1'
    started_at = [DateTimeOffset]::Now.ToString('o')
    policy = 'each API-clean Global2 client trains 134 tasks, generates local B3 under three-delete/one-add, validates 134 tasks, then stops; no Global3'
    processes = $records
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runRoot 'background_launch.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 6
