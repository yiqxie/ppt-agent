<#
.SYNOPSIS
  一键部署 PPT Slide Agent 到 Azure（PowerShell 版本）。
.DESCRIPTION
  会做的事：
    1. 创建（或重用）资源组
    2. 用 Bicep 部署 Storage / PostgreSQL / App Service
    3. 用 docker buildx 构建镜像并推送到 GHCR
    4. 配置 Web App 拉取该镜像
.PARAMETER ResourceGroup
  资源组名（默认 rg-ppt-agent）
.PARAMETER Location
  Azure 区域（默认 eastus2，与 yiqxie-ai 同区降低延迟）
.PARAMETER Image
  容器镜像 tag（默认 ghcr.io/yiqxie/ppt-agent:latest）
.PARAMETER PgPassword
  PostgreSQL 管理员密码；不传则会随机生成并打印
#>
param(
  [string]$ResourceGroup = "rg-ppt-agent",
  [string]$Location = "eastus2",
  [string]$Image = "ghcr.io/yiqxie/ppt-agent:latest",
  [string]$PgPassword = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSCommandPath)
Set-Location ..

if (-not $PgPassword) {
  Add-Type -AssemblyName 'System.Web'
  $PgPassword = [System.Web.Security.Membership]::GeneratePassword(24, 6)
  Write-Host "已生成随机 PG 密码：$PgPassword (请妥善保存)" -ForegroundColor Yellow
}

Write-Host "==> 1) 确保资源组 $ResourceGroup 存在 ($Location)" -ForegroundColor Cyan
az group create -n $ResourceGroup -l $Location -o table | Out-Null

Write-Host "==> 2) 部署 Bicep" -ForegroundColor Cyan
az deployment group create `
  --resource-group $ResourceGroup `
  --template-file infra/main.bicep `
  --parameters infra/main.parameters.json `
  --parameters pgAdminPassword="$PgPassword" containerImage="$Image" `
  --query "properties.outputs" `
  -o json | Tee-Object -Variable deployOut

$outputs = $deployOut | ConvertFrom-Json
$webAppName = $outputs.webAppName.value
$hostname = $outputs.webAppHostname.value
Write-Host "Web App: $webAppName · https://$hostname" -ForegroundColor Green

Write-Host "==> 3) 构建并推送镜像 $Image" -ForegroundColor Cyan
docker build -t $Image .
docker push $Image

Write-Host "==> 4) 让 Web App 拉取最新镜像" -ForegroundColor Cyan
az webapp config container set `
  --resource-group $ResourceGroup `
  --name $webAppName `
  --container-image-name $Image | Out-Null

az webapp restart -g $ResourceGroup -n $webAppName | Out-Null

Write-Host ""
Write-Host "✅ 部署完成！访问：https://$hostname" -ForegroundColor Green
Write-Host "如果首次启动较慢，可观察容器日志：" -ForegroundColor Yellow
Write-Host "  az webapp log tail -g $ResourceGroup -n $webAppName" -ForegroundColor Yellow
