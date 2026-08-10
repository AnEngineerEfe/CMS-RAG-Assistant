param(
    [string]$HostName = "localhost",
    [int]$Port = 5432,
    [string]$Database = "cms_rag_eval",
    [string]$User = "postgres"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$securePassword = Read-Host "PostgreSQL parolası ($User@$HostName`:$Port/$Database)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $env:PGVECTOR_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    Push-Location $projectRoot

    try {
        & $python -m scripts.run_chunk_lineage_evaluation `
            --backend pgvector `
            --host $HostName `
            --port $Port `
            --database $Database `
            --user $User `
            --output evaluation\results\pgvector-lineage-latest
        if ($LASTEXITCODE -ne 0) {
            throw "pgvector Seri 1 değerlendirmesi başarısız oldu."
        }

        & $python -m scripts.run_chunk_lineage_evaluation `
            --backend pgvector `
            --host $HostName `
            --port $Port `
            --database $Database `
            --user $User `
            --dataset evaluation\datasets\chunk_lineage_20_round2.json `
            --output evaluation\results\pgvector-lineage-round2
        if ($LASTEXITCODE -ne 0) {
            throw "pgvector Seri 2 değerlendirmesi başarısız oldu."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item Env:PGVECTOR_PASSWORD -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

Write-Host "pgvector 20+20 vaka değerlendirmesi tamamlandı."
