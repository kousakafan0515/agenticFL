$ErrorActionPreference = 'Stop'
$runRoot = 'D:\skillMAS\stage2_local_v9\runs\client_a_generation_01_20261013_r1'
$scriptPath = '/mnt/d/skillMAS/stage2_local_v9/scripts/run_client_a_b1_to_b5_with_local_secrets.sh'
$stdoutPath = Join-Path $runRoot 'B1_to_B5.launch.stdout.log'
$stderrPath = Join-Path $runRoot 'B1_to_B5.launch.stderr.log'
$statusPath = Join-Path $runRoot 'B1_to_B5.launch.status.json'

foreach ($path in @($stdoutPath, $stderrPath, $statusPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing launch artifact: $path"
    }
}

$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', $scriptPath) `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

$status = [ordered]@{
    schema_version = 'stage2_local_v9.client_a_b1_to_b5_launch.v1'
    status = 'started'
    started_at = [DateTimeOffset]::Now.ToString('o')
    windows_pid = $process.Id
    parent_bank = 'Client A original v9 B1'
    parent_bank_file_sha256 = 'sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4'
    stop_after = 'B5_validation'
    stdout = $stdoutPath
    stderr = $stderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
$status | ConvertTo-Json -Depth 4
