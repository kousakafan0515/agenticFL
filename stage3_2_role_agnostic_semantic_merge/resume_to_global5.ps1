$ErrorActionPreference = 'Stop'
$controllerRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_full_skillbank_to_global5_20261015_r1'
$statePath = Join-Path $controllerRoot 'controller_state.json'
$stdout = Join-Path $controllerRoot 'resume_001.stdout.log'
$stderr = Join-Path $controllerRoot 'resume_001.stderr.log'
$status = Join-Path $controllerRoot 'resume_001.launch.json'
foreach ($path in @($stdout, $stderr, $status)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite resume artifact: $path" }
}
$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
if ($state.status -ne 'failed' -or $state.failed_at_step -ne 'validate_Global3') {
    throw 'Resume requires failed/validate_Global3 state'
}
$global = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_local_b3_global3_20261015_r1\global_skillbank3.json'
$summary = Get-Content -Raw -Encoding UTF8 -LiteralPath 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_local_b3_global3_20261015_r1\summary.json' | ConvertFrom-Json
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $global).Hash.ToLowerInvariant()
$expected = ([string]$summary.global_skillbank.file_sha256).Replace('sha256:', '')
if ($actual -ne $expected) { throw 'Frozen Global3 hash mismatch before resume' }
$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_to_global5_with_secrets.sh', '--resume') `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru
[ordered]@{schema_version='stage3_2.global5_resume_launch.v1';started_at=[DateTimeOffset]::Now.ToString('o');windows_pid=$process.Id;resume_from='validate_Global3';reuses_global3=$true;global3_sha256='sha256:'+$actual;stdout=$stdout;stderr=$stderr} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $status -Encoding utf8
