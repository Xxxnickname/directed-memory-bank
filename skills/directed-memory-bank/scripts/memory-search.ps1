# 本地混合检索包装：设置 UTF-8 输出与可选镜像后调用 memory_search.py
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Query,
    [int]$Top = 8
)

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'memory_search.py'

# 受限网络可用镜像下载模型；已配好本地模型目录时此项无影响
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

& python $script search -q $Query -k $Top
exit $LASTEXITCODE
