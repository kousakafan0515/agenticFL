$ErrorActionPreference = 'Stop'
$runsRoot = 'D:\skillMAS\stage2_local_v9\runs'
$runRoot = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1'
$scriptPath = '/mnt/d/skillMAS/stage2_local_v9/scripts/run_client_a_patch_to_b5_with_local_secrets.sh'
$artifactStem = Join-Path $runsRoot 'client_a_b1_patch3_to_b5_20261015_r1.launch'
$stdoutPath = "$artifactStem.stdout.log"
$stderrPath = "$artifactStem.stderr.log"
$statusPath = "$artifactStem.status.json"

foreach ($path in @($stdoutPath, $stderrPath, $statusPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing launch artifact: $path"
    }
}
if ((Test-Path -LiteralPath $runRoot) -and (Get-ChildItem -LiteralPath $runRoot -Force | Select-Object -First 1)) {
    throw "Refusing to use a non-empty run root: $runRoot"
}

$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', $scriptPath) `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

$status = [ordered]@{
    schema_version = 'stage2_local_v9.client_a_patch3_launch.v1'
    status = 'started'
    started_at = [DateTimeOffset]::Now.ToString('o')
    windows_pid = $process.Id
    run_root = $runRoot
    parent_bank = 'Client A original v9 B1'
    parent_bank_file_sha256 = 'sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4'
    capacity_policy = 'whole-client ADD <= floor(distinct DELETE / 3); UPDATE is quota-neutral'
    stop_after = 'B5_validation'
    stdout = $stdoutPath
    stderr = $stderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
$status | ConvertTo-Json -Depth 4
