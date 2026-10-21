$ErrorActionPreference = 'Stop'
$controllerRoot = 'D:\skillMAS\stage3_2_role_agnostic_semantic_merge\runs\v9_full_skillbank_to_global5_20261015_r1'
$stdout = Join-Path $controllerRoot 'background.stdout.log'
$stderr = Join-Path $controllerRoot 'background.stderr.log'
if (Test-Path -LiteralPath $controllerRoot) {
    throw "Refusing to overwrite existing controller root: $controllerRoot"
}
New-Item -ItemType Directory -Path $controllerRoot | Out-Null
$process = Start-Process -FilePath 'wsl.exe' `
    -ArgumentList @('bash', '/mnt/d/skillMAS/stage3_2_role_agnostic_semantic_merge/run_to_global5_with_secrets.sh') `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru
[ordered]@{
    schema_version = 'stage3_2.full_skillbank_to_global5_launch.v1'
    started_at = [DateTimeOffset]::Now.ToString('o')
    windows_pid = $process.Id
    stdout = $stdout
    stderr = $stderr
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $controllerRoot 'launch_manifest.json') -Encoding UTF8
