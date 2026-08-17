$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mcpModule = Join-Path $projectRoot "mcp-swing-demo"
$mcpJar = Join-Path $mcpModule "target\mcp-swing-demo.jar"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python sanal ortamı bulunamadı. Önce README kurulum adımlarını uygulayın."
}

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "Java bulunamadı. Java 21 JDK kurup PATH değişkenine ekleyin."
}

if (-not (Test-Path -LiteralPath $mcpJar)) {
    Write-Host "MCP Swing modülü ilk kez derleniyor..."
    # Bazı sadeleştirilmiş VS Code terminallerinde System32 PATH'ten düşebildiği için
    # Maven Wrapper'ın kullandığı cmd.exe yolunu çalışma süreciyle sınırlı tamamlarız.
    $env:Path = "$env:SystemRoot\System32;$env:Path"
    & (Join-Path $mcpModule "mvnw.cmd") -f (Join-Path $mcpModule "pom.xml") clean verify
    if ($LASTEXITCODE -ne 0) {
        throw "MCP Swing modülü derlenemedi."
    }
}

Set-Location -LiteralPath $projectRoot
& $python -m streamlit run app.py
