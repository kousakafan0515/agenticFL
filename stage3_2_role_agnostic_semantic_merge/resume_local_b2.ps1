$ErrorActionPreference = 'Stop'

$runRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_global1_to_local_b2_20261014_r1'
$scriptPath = '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_client_to_b2_with_secrets.sh'
$records = @()

foreach ($client in @('A', 'B', 'C')) {
    $clientRoot = Join-Path $runRoot "client_$client"
    $statePath = Join-Path $clientRoot 'controller_state.json'
    if (-not (Test-Path -LiteralPath $statePath)) {
        throw "Missing controller state for Client $client"
    }
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    if ($state.status -ne 'failed') {
        throw "Client $client is not in failed state: $($state.status)"
    }
    $attempt = 1
    do {
        $stdout = Join-Path $runRoot ("client_{0}.resume_{1:D3}.stdout.log" -f $client, $attempt)
        $stderr = Join-Path $runRoot ("client_{0}.resume_{1:D3}.stderr.log" -f $client, $attempt)
        $attempt++
    } while ((Test-Path -LiteralPath $stdout) -or (Test-Path -LiteralPath $stderr))
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
    }
}

$manifest = [ordered]@{
    schema_version = 'stage3_2.local_b2_background_resume.v1'
    resumed_at = [DateTimeOffset]::Now.ToString('o')
    policy = 'explicit checkpoint resume; preserve prior outputs; stop after B2'
    processes = $records
}
$manifestPath = Join-Path $runRoot 'resume_manifest_001.json'
if (Test-Path -LiteralPath $manifestPath) {
    throw "Refusing to overwrite resume manifest: $manifestPath"
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 5
