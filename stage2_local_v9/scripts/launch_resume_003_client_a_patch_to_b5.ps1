$ErrorActionPreference = 'Stop'
$runsRoot = 'D:\skillMAS\stage2_local_v9\runs'
$runRoot = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage2_local_v9/scripts/run_client_a_patch_to_b5_with_local_secrets.sh'
$artifactStem = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1.resume_003'
$stdoutPath = "$artifactStem.stdout.log"
$stderrPath = "$artifactStem.stderr.log"
$statusPath = "$artifactStem.status.json"
$statePath = Join-Path $runRoot 'controller_state.json'
$manifestPath = Join-Path $runRoot 'B3_bounded_recovery_preflight_manifest.json'

foreach ($path in @($stdoutPath, $stderrPath, $statusPath)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing resume artifact: $path" }
}
if (-not (Test-Path -LiteralPath $statePath)) { throw "Missing controller state: $statePath" }
$state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
if ($state.status -ne 'failed' -or $state.current_step -ne 'B3_teacher') {
    throw "Resume requires failed/B3_teacher state"
}
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $path = Join-Path $runRoot $entry.path
    $hash = 'sha256:' + (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($hash -ne $entry.sha256) { throw "Frozen B3 artifact changed: $($entry.path)" }
}
if (Get-ChildItem -LiteralPath $runRoot -Filter 'B3_patch_recovery_attempt_*.json') {
    throw 'Refusing to overwrite an existing bounded recovery attempt'
}

$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', $scriptPath, '--resume') `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

$status = [ordered]@{
    schema_version = 'stage2_local_v9.client_a_patch3_resume_launch.v1'
    status = 'started'
    started_at = [DateTimeOffset]::Now.ToString('o')
    windows_pid = $process.Id
    run_root = $runRoot
    resume_attempt = 3
    preserves_original_checkpoint_and_attempts = $true
    recovery_scope = 'B3_final_patch_only'
    final_recovery_attempts = 2
    role_scoped_target_allowlist = $true
    stop_after = 'B5_validation'
    stdout = $stdoutPath
    stderr = $stderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
$status | ConvertTo-Json -Depth 4
