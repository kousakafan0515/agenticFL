$ErrorActionPreference = 'Stop'

$runDirectory = 'D:\skillMAS\stage2_local_v9\runs'
$stdoutPath = Join-Path $runDirectory 'client_bc_generation_01_20261013_r3.resume.stdout.log'
$stderrPath = Join-Path $runDirectory 'client_bc_generation_01_20261013_r3.resume.stderr.log'
$statusPath = Join-Path $runDirectory 'client_bc_generation_01_20261013_r3.resume.status.json'
$startedAt = [DateTimeOffset]::Now.ToString('o')

try {
    $process = Start-Process -FilePath 'wsl.exe' `
        -ArgumentList @('bash', '/mnt/d/skillMAS/stage2_local_v9/scripts/resume_client_b_then_c_with_local_secrets.sh') `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    $status = [ordered]@{
        status = if ($process.ExitCode -eq 0) { 'complete' } else { 'failed' }
        exit_code = $process.ExitCode
        started_at = $startedAt
        finished_at = [DateTimeOffset]::Now.ToString('o')
        stdout = $stdoutPath
        stderr = $stderrPath
    }
} catch {
    $status = [ordered]@{
        status = 'launcher_error'
        error = $_.Exception.Message
        started_at = $startedAt
        finished_at = [DateTimeOffset]::Now.ToString('o')
        stdout = $stdoutPath
        stderr = $stderrPath
    }
}
$status | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
