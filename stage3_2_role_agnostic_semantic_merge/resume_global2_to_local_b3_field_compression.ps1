$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global2_to_local_b3_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_global2_to_local_b3_with_secrets.sh'
$records = @()
foreach ($client in @('B','C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $statePath = Join-Path $clientRoot 'controller_state.json'
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    if ($state.status -ne 'failed' -or $state.current_step -ne 'B3_teacher') {
        throw "Client $client is not stopped at failed/B3_teacher"
    }
    foreach ($attempt in 1..3) {
        $path = Join-Path $clientRoot ("B3_patch_attempt_{0:D2}.json" -f $attempt)
        if (-not (Test-Path -LiteralPath $path)) { throw "Missing frozen Client $client patch attempt: $path" }
    }
    foreach ($attempt in 1..2) {
        $path = Join-Path $clientRoot ("B3_patch_compression_{0:D2}.json" -f $attempt)
        if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite Client $client compression attempt: $path" }
    }
    $stdout = Join-Path $runRoot "client_$client.resume_001.stdout.log"
    $stderr = Join-Path $runRoot "client_$client.resume_001.stderr.log"
    foreach ($path in @($stdout,$stderr)) {
        if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite resume log: $path" }
    }
    $process = Start-Process -FilePath 'wsl.exe' -ArgumentList @('bash', $scriptPath, $client, 'resume') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $records += [ordered]@{client=$client;windows_pid=$process.Id;stdout=$stdout;stderr=$stderr;started_at=[DateTimeOffset]::Now.ToString('o');recovery='bounded_field_compression';max_attempts=2;target_characters=760}
}
$manifest = [ordered]@{schema_version='stage3_2.global2_to_local_b3_field_compression_resume.v1';started_at=[DateTimeOffset]::Now.ToString('o');preserves_training=$true;preserves_family_checkpoint=$true;preserves_patch_attempts_01_to_03=$true;processes=$records}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runRoot 'field_compression_resume_001.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 6
