$ErrorActionPreference = 'Stop'
$runsRoot = 'D:\skillMAS\stage2_local_v9\runs'
$runRoot = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage2_local_v9/scripts/run_client_a_patch_to_b5_with_local_secrets.sh'
$artifactStem = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1.resume_004'
$stdoutPath = "$artifactStem.stdout.log"
$stderrPath = "$artifactStem.stderr.log"
$statusPath = "$artifactStem.status.json"
$statePath = Join-Path $runRoot 'controller_state.json'
$checkpointPath = Join-Path $runRoot 'B3_teacher_record.checkpoint.json'
$frozenCheckpoint = Join-Path $runRoot 'B3_teacher_record.pre_split_D115.checkpoint.json'
$auditPath = Join-Path $runRoot 'B3_split_D115_preflight_manifest.json'

foreach ($path in @($stdoutPath, $stderrPath, $statusPath, $frozenCheckpoint, $auditPath)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing D-115 artifact: $path" }
}
$state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
if ($state.status -ne 'failed' -or $state.current_step -ne 'B3_teacher') {
    throw 'D-115 resume requires failed/B3_teacher state'
}
$required = @(
    'B3_teacher_record.checkpoint.json',
    'B3_patch_attempt_01.json', 'B3_patch_attempt_02.json', 'B3_patch_attempt_03.json',
    'B3_patch_recovery_attempt_01.json', 'B3_patch_recovery_attempt_02.json'
)
$files = @()
foreach ($name in $required) {
    $path = Join-Path $runRoot $name
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing frozen B3 artifact: $name" }
    $files += [ordered]@{ path = $name; sha256 = 'sha256:' + (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }
}
Copy-Item -LiteralPath $checkpointPath -Destination $frozenCheckpoint
$audit = [ordered]@{
    schema_version = 'stage2_local_v9.client_a_split_final_preflight.v1'
    created_at = [DateTimeOffset]::Now.ToString('o')
    policy = 'DELETE_UPDATE_then_program_quota_then_ADD_only'
    original_artifacts = $files
    frozen_checkpoint_copy = [ordered]@{
        path = [IO.Path]::GetFileName($frozenCheckpoint)
        sha256 = 'sha256:' + (Get-FileHash -Algorithm SHA256 -LiteralPath $frozenCheckpoint).Hash.ToLowerInvariant()
    }
}
$audit | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $auditPath -Encoding utf8

$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', $scriptPath, '--resume') `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru
$status = [ordered]@{
    schema_version = 'stage2_local_v9.client_a_split_final_resume_launch.v1'
    status = 'started'
    started_at = [DateTimeOffset]::Now.ToString('o')
    windows_pid = $process.Id
    resume_attempt = 4
    recovery_scope = 'B3_split_final_from_frozen_family_findings'
    preserves_prior_attempts = $true
    stop_after = 'B5_validation'
    stdout = $stdoutPath
    stderr = $stderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
$status | ConvertTo-Json -Depth 4
