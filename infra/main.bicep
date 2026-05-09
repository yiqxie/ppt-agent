// =====================================================================
// ppt-agent · Azure 部署 Bicep 模板（Container Apps + 低成本配置）
// 创建：
//   1. Storage Account（Standard_LRS）+ 3 个 blob 容器
//   2. PostgreSQL Flexible Server（Burstable B1ms）+ 数据库
//   3. Log Analytics Workspace + Container Apps Environment
//   4. Container App（带系统 MI、WebSocket、自动伸缩）
//   5. 角色：Container App MI -> Storage Blob Data Contributor + Delegator
// 复用已有：Azure OpenAI（yiqxie-ai，eastus2）
// =====================================================================

@description('部署的资源前缀（小写字母数字）')
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
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Microsoft Entra ID 租户 ID（启用认证时填写）')
param aadTenantId string = ''

@description('后端 API 应用 ID URI（启用认证时填写）')
param aadApiAudience string = ''

@description('启用 Microsoft Entra ID 认证')
param authEnabled bool = false

// ---------------- 计算变量 ----------------
var storageName = toLower('${namePrefix}st${uniqueString(resourceGroup().id)}')
var lawName = '${namePrefix}-law'
var envName = '${namePrefix}-env'
var appName = '${namePrefix}-app'
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

// 防火墙：允许 Azure 服务访问（Container Apps 出口 IP 不固定）
resource pgFwAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ---------------- Log Analytics + Container Apps Environment ----------------
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: lawName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ---------------- Container App ----------------
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: cae.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto' // 支持 HTTP/2 与 WebSocket
        allowInsecure: false
        traffic: [
          { latestRevision: true, weight: 100 }
        ]
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
        }
      }
      secrets: [
        {
          name: 'pg-conn'
          value: 'postgresql+asyncpg://${pgAdminUser}:${uriComponent(pgAdminPassword)}@${pg.properties.fullyQualifiedDomainName}:5432/${pgDbName}?ssl=require'
        }
        {
          name: 'openai-key'
          value: listKeys(resourceId(openAiSubscriptionId, openAiResourceGroup, 'Microsoft.CognitiveServices/accounts', openAiAccountName), '2024-04-01-preview').key1
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'DEBUG', value: 'false' }
            { name: 'PORT', value: '8000' }
            { name: 'AZURE_STORAGE_ACCOUNT', value: storage.name }
            { name: 'AZURE_CONTAINER_SCREENSHOTS', value: 'screenshots' }
            { name: 'AZURE_CONTAINER_PROMPTS', value: 'prompts' }
            { name: 'AZURE_CONTAINER_UPLOADS', value: 'uploads' }
            { name: 'DATABASE_URL', secretRef: 'pg-conn' }
            { name: 'AZURE_OPENAI_ENDPOINT', value: 'https://${openAiAccountName}.openai.azure.com/' }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' }
            { name: 'AZURE_OPENAI_API_VERSION', value: openAiApiVersion }
            { name: 'AZURE_OPENAI_VISION_DEPLOYMENT', value: openAiDeployment }
            { name: 'AUTH_ENABLED', value: string(authEnabled) }
            { name: 'AAD_TENANT_ID', value: aadTenantId }
            { name: 'AAD_API_AUDIENCE', value: aadApiAudience }
            { name: 'AAD_REQUIRED_SCOPE', value: 'access_as_user' }
            { name: 'CORS_ORIGINS', value: '["*"]' }
            { name: 'MAX_CONCURRENT_SLIDE_JOBS', value: '2' }
            { name: 'MAX_CONCURRENT_SLIDE_PAGES', value: '4' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 15
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scale'
            http: { metadata: { concurrentRequests: '50' } }
          }
        ]
      }
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

// ---------------- 角色分配：MI 访问 Storage ----------------
var roleStorageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource raStorageBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, app.id, roleStorageBlobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageBlobDataContributor)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

var roleStorageBlobDelegator = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
resource raStorageDelegator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, app.id, roleStorageBlobDelegator)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageBlobDelegator)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------- 输出 ----------------
output appName string = app.name
output appFqdn string = app.properties.configuration.ingress.fqdn
output appPrincipalId string = app.identity.principalId
output storageAccountName string = storage.name
output postgresFqdn string = pg.properties.fullyQualifiedDomainName
output postgresDb string = pgDbName
output environmentName string = cae.name
