$ErrorActionPreference = 'Stop'
$runsRoot = 'D:\skillMAS\stage2_local_v9\runs'
$runRoot = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage2_local_v9/scripts/run_client_a_patch_to_b5_with_local_secrets.sh'
$artifactStem = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1.resume_001'
$stdoutPath = "$artifactStem.stdout.log"
$stderrPath = "$artifactStem.stderr.log"
$statusPath = "$artifactStem.status.json"
$statePath = Join-Path $runRoot 'controller_state.json'

foreach ($path in @($stdoutPath, $stderrPath, $statusPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing resume artifact: $path"
    }
}
if (-not (Test-Path -LiteralPath $statePath)) {
    throw "Missing controller state: $statePath"
}
$state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
if ($state.status -ne 'failed') {
    throw "Resume requires failed controller state, got: $($state.status)"
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
    resume_attempt = 1
    preserves_failure_history = $true
    requested_max_tokens = 16000
    truncation_retries = 2
    response_format = 'json_object'
    stop_after = 'B5_validation'
    stdout = $stdoutPath
    stderr = $stderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
$status | ConvertTo-Json -Depth 4
