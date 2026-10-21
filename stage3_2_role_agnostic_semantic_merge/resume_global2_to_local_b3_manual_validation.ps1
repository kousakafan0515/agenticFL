$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global2_to_local_b3_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_global2_to_local_b3_with_secrets.sh'
$records = @()
foreach ($client in @('B','C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $state = Get-Content -Raw -LiteralPath (Join-Path $clientRoot 'controller_state.json') | ConvertFrom-Json
    if ($state.status -ne 'failed' -or $state.current_step -ne 'B3_teacher') {
        throw "Client $client is not stopped at failed/B3_teacher"
    }
    foreach ($name in @('B3_skillbank.json','B3_patch.json','B3_teacher_record.json','B3_manual_field_repair_audit.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $clientRoot $name))) {
            throw "Missing validated manual-repair output for Client $client`: $name"
        }
    }
    $audit = Get-Content -Raw -LiteralPath (Join-Path $clientRoot 'B3_manual_field_repair_audit.json') | ConvertFrom-Json
    if ($audit.policy -ne 'human_reviewed_targeted_compression_no_teacher_call') {
        throw "Unexpected repair policy for Client $client"
    }
    $stdout = Join-Path $runRoot "client_$client.resume_004.stdout.log"
    $stderr = Join-Path $runRoot "client_$client.resume_004.stderr.log"
    foreach ($path in @($stdout,$stderr)) {
        if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite resume log: $path" }
    }
    $process = Start-Process -FilePath 'wsl.exe' `
        -ArgumentList @('bash', $scriptPath, $client, 'resume') `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    $records += [ordered]@{
        client = $client
        windows_pid = $process.Id
        stdout = $stdout
        stderr = $stderr
        started_at = [DateTimeOffset]::Now.ToString('o')
        recovery = 'human_reviewed_targeted_compression_no_teacher_call'
        next_step = 'B3_validation'
    }
}
$manifest = [ordered]@{
    schema_version = 'stage3_2.global2_to_local_b3_manual_validation_resume.v1'
    started_at = [DateTimeOffset]::Now.ToString('o')
    preserves_checkpoints_and_teacher_attempts = $true
    teacher_calls_disabled_by_existing_validated_outputs = $true
    processes = $records
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runRoot 'manual_validation_resume_004.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 6
