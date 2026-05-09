// =====================================================================
// ppt-agent · Azure 部署 Bicep 模板（最低成本配置）
// 创建：
//   1. Storage Account（Standard_LRS）+ 三个 blob 容器
//   2. PostgreSQL Flexible Server（Burstable B1ms）+ 数据库
//   3. App Service Plan（Linux B1）+ Web App for Containers
//   4. Web App 系统分配的 Managed Identity 授权访问 Storage
// 复用已有：Azure OpenAI（yiqxie-ai，eastus2）
// =====================================================================

@description('部署的资源前缀')
param namePrefix string = 'pptagent'

@description('部署区域')
param location string = resourceGroup().location

@description('PostgreSQL 管理员账号')
@minLength(4)
param pgAdminUser string = 'pgadmin'

@description('PostgreSQL 管理员密码')
@secure()
param pgAdminPassword string

@description('Azure OpenAI 资源所在订阅')
param openAiSubscriptionId string = subscription().subscriptionId

@description('Azure OpenAI 资源组名称')
param openAiResourceGroup string = 'OpenAI'

@description('Azure OpenAI 账户名称')
param openAiAccountName string = 'yiqxie-ai'

@description('Azure OpenAI 视觉模型部署名')
param openAiDeployment string = 'gpt-4o'

@description('Azure OpenAI API 版本')
param openAiApiVersion string = '2024-10-21'

@description('容器镜像 (registry/image:tag)')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Microsoft Entra ID 租户 ID（启用认证时填写）')
param aadTenantId string = ''

@description('后端 API 应用 ID URI（启用认证时填写）')
param aadApiAudience string = ''

@description('启用 Microsoft Entra ID 认证')
param authEnabled bool = false

// ---------------- 计算变量 ----------------
// Storage 名称必须 3-24 字符，全小写字母数字
var storageName = toLower('${namePrefix}st${uniqueString(resourceGroup().id)}')
var planName = '${namePrefix}-plan'
var webAppName = '${namePrefix}-web-${uniqueString(resourceGroup().id)}'
var pgServerName = '${namePrefix}-pg-${uniqueString(resourceGroup().id)}'
var pgDbName = 'ppt_agent'

// ---------------- Storage ----------------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    cors: {
      corsRules: [
        {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'HEAD']
          allowedHeaders: ['*']
          exposedHeaders: ['*']
          maxAgeInSeconds: 3600
        }
      ]
    }
  }
}

resource containerScreenshots 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'screenshots'
  properties: { publicAccess: 'None' }
}
resource containerPrompts 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'prompts'
  properties: { publicAccess: 'None' }
}
resource containerUploads 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'uploads'
  properties: { publicAccess: 'None' }
}

// ---------------- PostgreSQL Flexible Server (B1ms) ----------------
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: pgServerName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: pg
  name: pgDbName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// 防火墙：允许 Azure 服务（App Service 出口 IP 不固定）
resource pgFwAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ---------------- App Service Plan (B1 Linux) ----------------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: { name: 'B1', tier: 'Basic' }
  kind: 'linux'
  properties: { reserved: true }
}

// ---------------- Web App (Container) ----------------
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux,container'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${containerImage}'
      alwaysOn: true
      ftpsState: 'Disabled'
      http20Enabled: true
      webSocketsEnabled: true
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://ghcr.io' }
        { name: 'ENVIRONMENT', value: 'production' }
        { name: 'DEBUG', value: 'false' }
        { name: 'AZURE_STORAGE_ACCOUNT', value: storage.name }
        { name: 'AZURE_CONTAINER_SCREENSHOTS', value: 'screenshots' }
        { name: 'AZURE_CONTAINER_PROMPTS', value: 'prompts' }
        { name: 'AZURE_CONTAINER_UPLOADS', value: 'uploads' }
        {
          name: 'DATABASE_URL'
          value: 'postgresql+asyncpg://${pgAdminUser}:${uriComponent(pgAdminPassword)}@${pg.properties.fullyQualifiedDomainName}:5432/${pgDbName}?ssl=require'
        }
        { name: 'AZURE_OPENAI_ENDPOINT', value: 'https://${openAiAccountName}.openai.azure.com/' }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: listKeys(resourceId(openAiSubscriptionId, openAiResourceGroup, 'Microsoft.CognitiveServices/accounts', openAiAccountName), '2024-04-01-preview').key1
        }
        { name: 'AZURE_OPENAI_API_VERSION', value: openAiApiVersion }
        { name: 'AZURE_OPENAI_VISION_DEPLOYMENT', value: openAiDeployment }
        { name: 'AUTH_ENABLED', value: string(authEnabled) }
        { name: 'AAD_TENANT_ID', value: aadTenantId }
        { name: 'AAD_API_AUDIENCE', value: aadApiAudience }
        { name: 'AAD_REQUIRED_SCOPE', value: 'access_as_user' }
        { name: 'CORS_ORIGINS', value: '["https://${webAppName}.azurewebsites.net"]' }
        { name: 'MAX_CONCURRENT_SLIDE_JOBS', value: '2' }
        { name: 'MAX_CONCURRENT_SLIDE_PAGES', value: '4' }
      ]
    }
  }
  dependsOn: [
    containerScreenshots
    containerPrompts
    containerUploads
    pgDb
    pgFwAzure
  ]
}

// ---------------- 角色分配：Web App MI 访问 Storage Blob ----------------
// Storage Blob Data Contributor
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource roleStorageBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, webApp.id, storageBlobDataContributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Delegator（生成 User Delegation Key 用）
var storageBlobDelegatorRoleId = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
resource roleStorageDelegator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, webApp.id, storageBlobDelegatorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDelegatorRoleId)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------- 输出 ----------------
output webAppName string = webApp.name
output webAppHostname string = webApp.properties.defaultHostName
output webAppPrincipalId string = webApp.identity.principalId
output storageAccountName string = storage.name
output postgresFqdn string = pg.properties.fullyQualifiedDomainName
output postgresDb string = pgDbName
