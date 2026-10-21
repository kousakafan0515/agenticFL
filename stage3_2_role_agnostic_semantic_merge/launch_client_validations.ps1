$ErrorActionPreference = 'Stop'

$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_b1_round1_client_validation_20261014_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_client_global_validation.sh'
$launchManifest = Join-Path $runRoot 'background_launch_manifest.json'
if (Test-Path -LiteralPath $launchManifest) {
    throw "Refusing to overwrite existing launch manifest: $launchManifest"
}

$startedAt = [DateTimeOffset]::Now.ToString('o')
$records = @()
foreach ($client in @('A', 'B', 'C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $stdoutPath = Join-Path $clientRoot 'background.stdout.log'
    $stderrPath = Join-Path $clientRoot 'background.stderr.log'
    $statusPath = Join-Path $clientRoot 'background_status.json'
    if ((Test-Path -LiteralPath $stdoutPath) -or (Test-Path -LiteralPath $stderrPath) -or (Test-Path -LiteralPath $statusPath) -or (Test-Path -LiteralPath (Join-Path $clientRoot 'validation'))) {
        throw "Refusing to overwrite existing Client $client background state"
    }
    $process = Start-Process -FilePath 'wsl.exe' `
        -ArgumentList @('bash', $scriptPath, $client) `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru
    $records += [ordered]@{
        client = $client
        windows_pid = $process.Id
        stdout = $stdoutPath
        stderr = $stderrPath
        status = $statusPath
    }
}

$manifest = [ordered]@{
    schema_version = 'stage3_2.client_validation_background_launch.v1'
    started_at = $startedAt
    launch_policy = 'three independent hidden WSL processes; no automatic restart'
    processes = $records
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $launchManifest -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6
