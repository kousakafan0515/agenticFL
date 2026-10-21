$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global2_to_local_b3_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_global2_to_local_b3_with_secrets.sh'
$records = @()
foreach ($client in @('B','C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $state = Get-Content -Raw -LiteralPath (Join-Path $clientRoot 'controller_state.json') | ConvertFrom-Json
    if ($state.status -ne 'failed' -or $state.current_step -ne 'B3_teacher') { throw "Client $client is not stopped at failed/B3_teacher" }
    foreach ($attempt in 1..3) {
        if (-not (Test-Path -LiteralPath (Join-Path $clientRoot ("B3_patch_attempt_{0:D2}.json" -f $attempt)))) { throw "Missing frozen patch attempt for Client $client" }
    }
    foreach ($attempt in 1..2) {
        if (-not (Test-Path -LiteralPath (Join-Path $clientRoot ("B3_patch_compression_{0:D2}.json" -f $attempt)))) { throw "Missing D-109 compression attempt for Client $client" }
        if (Test-Path -LiteralPath (Join-Path $clientRoot ("B3_patch_replacement_compression_{0:D2}.json" -f $attempt))) { throw "Refusing to overwrite replacement compression attempt for Client $client" }
    }
    $stdout = Join-Path $runRoot "client_$client.resume_002.stdout.log"
    $stderr = Join-Path $runRoot "client_$client.resume_002.stderr.log"
    foreach ($path in @($stdout,$stderr)) { if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite resume log: $path" } }
    $process = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash', $scriptPath, $client, 'resume') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$process.Id;stdout=$stdout;stderr=$stderr;started_at=[DateTimeOffset]::Now.ToString('o');recovery='replacement_table_field_compression';max_attempts=2;target_characters=760}
}
$manifest = [ordered]@{schema_version='stage3_2.global2_to_local_b3_replacement_compression_resume.v1';started_at=[DateTimeOffset]::Now.ToString('o');preserves_all_prior_attempts=$true;processes=$records}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runRoot 'replacement_compression_resume_002.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 6
