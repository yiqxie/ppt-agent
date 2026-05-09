# PPT Slide Agent

> 把每一页 PPT 自动变成可复用的 prompt 模板 —— 一站式上传、AI 解析、检索、复用与管理。

[![Build & Push](https://github.com/yiqxie/ppt-agent/actions/workflows/build.yml/badge.svg)](https://github.com/yiqxie/ppt-agent/actions/workflows/build.yml)

---

## 🌟 项目简介

**PPT Slide Agent** 是一个端到端的 Web 应用，可以让用户：

1. **上传一个或多个 PPT 文件**（.ppt/.pptx）。
2. Agent **自动**：
   - 把 PPT 每一页渲染成截图
   - 用 **Azure OpenAI（GPT-4o 视觉模型）** 提取该 slide 的 **风格、配色、字体、布局、配图** 等设计信息
   - 把每页的 **截图** 与 **prompt JSON** 存入 **Azure Storage Blob**
   - 把 **路径关系、prompt、tag、结构化样式** 写入 **Azure Database for PostgreSQL**
3. 通过现代化 React UI **实时查看处理进度**、**搜索 / 预览 / 编辑 prompt 与 tag**、**批量删除**。
4. 部署到 **Azure App Service for Containers**，使用 **Microsoft Entra ID** 登录保护。

> 适合做 **PPT 设计稿库**、**AI 生成式参考素材库**、**销售/营销内容审计** 等场景。

---

## 🧭 目录

- [功能亮点](#-功能亮点)
- [系统架构](#-系统架构)
- [仓库结构](#-仓库结构)
- [快速开始（本地）](#-快速开始本地)
- [部署到 Azure](#-部署到-azure)
- [Microsoft Entra ID 配置](#-microsoft-entra-id-配置)
- [API 一览](#-api-一览)
- [关键技术决策](#-关键技术决策)
- [开发与扩展](#-开发与扩展)

---

## ✨ 功能亮点

| 模块 | 能力 |
|---|---|
| 上传 | 拖拽 / 多文件 / 进度条 / 文件类型校验 |
| 处理 | LibreOffice headless 渲染 + GPT-4o 视觉分析 + 异步并发 + 自动重试 |
| 实时进度 | WebSocket 双向推送（带自动重连与心跳）|
| 检索 | 关键字（标题/摘要/prompt 全文）+ tag 精确过滤 + 任务过滤 |
| 编辑 | 在线修改标题、摘要、prompt 模板、tag |
| 批量 | 多选 + 批量删除（同步删除 Blob 与 DB 记录）|
| 鉴权 | Microsoft Entra ID（MSAL.js）+ 后端 JWT 校验，可一键关闭 |
| 主题 | 浅色 + 渐变 hero + 现代圆角 + 中英文字体栈 |
| 部署 | 单 Docker 镜像（含 LibreOffice）+ Bicep IaC 一键拉起 |

---

## 🏗 系统架构

```mermaid
flowchart LR
    subgraph Client["浏览器"]
      UI["React + MUI<br/>(Vite SPA)"]
    end
    UI -- "REST / WebSocket" --> API["FastAPI<br/>(uvicorn)"]
    API -->|asyncpg| PG[("Azure PostgreSQL<br/>Flexible Server")]
    API -->|"上传/SAS"| Blob[("Azure Storage<br/>Blob: screenshots/prompts/uploads")]
    API -->|"PPT->PDF"| LO["LibreOffice<br/>headless"]
    LO -->|"PDF->PNG"| API
    API -->|"vision"| AOAI["Azure OpenAI<br/>GPT-4o"]
    UI -- "MSAL" --> AAD["Microsoft Entra ID"]
    API -- "JWT 校验" --> AAD
```

**部署形态**：单 Docker 镜像同时托管 FastAPI 后端 + Vite 构建后的前端静态资源，跑在 Azure App Service for Containers (Linux B1) 上；
PostgreSQL 用 Burstable B1ms，Storage 用 Standard LRS，整套月成本约 **20-40 USD**（含 OpenAI 复用既有资源）。

---

## 📁 仓库结构

```
ppt-agent/
├── backend/                       # FastAPI 后端
│   ├── app/
│   │   ├── api/                   # REST + WebSocket 路由
│   │   │   ├── jobs.py            # 上传/Job CRUD
│   │   │   ├── slides.py          # Slide 检索/编辑/批量删除
│   │   │   └── websocket.py       # 进度 WebSocket
│   │   ├── core/                  # 配置/日志/JWT 校验
│   │   ├── db/                    # SQLAlchemy 引擎与 session
│   │   ├── models/                # ORM 模型
│   │   ├── schemas/               # Pydantic Schema
│   │   ├── services/              # 业务服务
│   │   │   ├── storage.py         # Azure Blob 封装
│   │   │   ├── ai.py              # Azure OpenAI 视觉分析
│   │   │   ├── ppt_renderer.py    # LibreOffice + pdf2image
│   │   │   ├── progress.py        # WebSocket 广播
│   │   │   └── orchestrator.py    # 端到端编排
│   │   └── main.py                # FastAPI 入口
│   ├── requirements.txt
│   └── .env.example
├── frontend/                      # React + Vite + MUI
│   ├── src/
│   │   ├── api/                   # 类型 + axios 客户端
│   │   ├── auth/                  # MSAL.js 集成
│   │   ├── components/            # 可复用 UI 组件
│   │   ├── hooks/                 # WebSocket 等 hook
│   │   ├── pages/                 # 4 个核心页面
│   │   ├── theme/                 # MUI 主题
│   │   └── main.tsx               # 路由入口
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── infra/
│   ├── main.bicep                 # 全部 Azure 资源 IaC
│   ├── main.parameters.json
│   └── deploy.ps1                 # 一键部署脚本
├── .github/workflows/build.yml    # GHCR 构建推送
├── Dockerfile                     # 多阶段构建（含 LibreOffice）
├── .dockerignore
├── .gitignore
└── README.md
```

---

## 🚀 快速开始（本地）

### 0. 先决条件

| 工具 | 用途 | 备注 |
|---|---|---|
| Python ≥ 3.11 | 后端 | 推荐 3.12 |
| Node.js ≥ 20 | 前端 | |
| Docker Desktop | 本地容器调试 | 可选 |
| LibreOffice | PPT 渲染 | Windows 可安装到默认路径，或设 `SOFFICE_BIN` |
| Poppler | PDF 渲染 | Windows: 从 [poppler-windows](https://github.com/oschwartz10612/poppler-windows) 下载，设 `POPPLER_PATH` |
| PostgreSQL ≥ 14 | 本地数据库 | 也可直接连 Azure 上的实例 |

### 1. 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# 编辑 .env，至少填入：
#   DATABASE_URL（指向本地或 Azure 上的 PG）
#   AZURE_STORAGE_CONNECTION_STRING（Azurite 或真实 storage）
#   AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_VISION_DEPLOYMENT

uvicorn app.main:app --reload --port 8000
```

> Windows 下若找不到 LibreOffice 或 poppler：
> ```powershell
> $env:SOFFICE_BIN = "C:\Program Files\LibreOffice\program\soffice.exe"
> $env:POPPLER_PATH = "C:\poppler-23.11.0\Library\bin"
> ```

### 2. 前端

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
# 访问 http://localhost:5173
```

Vite 会把 `/api` 与 `/ws` 反向代理到 `http://localhost:8000`。

### 3. 用 Docker 一键起完整环境

```powershell
docker build -t ppt-agent:dev .
docker run --rm -it -p 8000:8000 `
  -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/ppt_agent" `
  -e AZURE_STORAGE_CONNECTION_STRING="..." `
  -e AZURE_OPENAI_ENDPOINT="https://yiqxie-ai.openai.azure.com/" `
  -e AZURE_OPENAI_API_KEY="<key>" `
  -e AZURE_OPENAI_VISION_DEPLOYMENT="gpt-4o" `
  ppt-agent:dev
# 访问 http://localhost:8000
```

---

## ☁️ 部署到 Azure

### 方式一：一键脚本

```powershell
# 1) 登录 Azure 与设置订阅
az login
az account set --subscription "<your-subscription>"

# 2) 一键部署（资源组 + 资源 + 推镜像 + 配置 Web App）
cd ppt-agent
.\infra\deploy.ps1 -ResourceGroup rg-ppt-agent -Location eastus2 -Image ghcr.io/yiqxie/ppt-agent:latest
```

执行完会输出网站地址，例如：
```
✅ 部署完成！访问：https://pptagent-web-xxxx.azurewebsites.net
```

### 方式二：手动 Bicep + 推镜像

```powershell
# 1) 创建资源组
az group create -n rg-ppt-agent -l eastus2

# 2) 部署资源
az deployment group create `
  --resource-group rg-ppt-agent `
  --template-file infra/main.bicep `
  --parameters infra/main.parameters.json `
  --parameters pgAdminPassword='Strong-P@ssw0rd!' containerImage='ghcr.io/yiqxie/ppt-agent:latest'

# 3) 构建并推送镜像（GHCR 需先 docker login ghcr.io）
docker build -t ghcr.io/yiqxie/ppt-agent:latest .
docker push ghcr.io/yiqxie/ppt-agent:latest

# 4) 触发 Web App 拉取最新镜像
az webapp restart -g rg-ppt-agent -n <webAppName>
```

### 资源说明（按月成本）

| 资源 | SKU | 月成本（USD，估算） |
|---|---|---|
| App Service Plan | Linux B1 | ~13 |
| PostgreSQL Flexible | Burstable B1ms (32GB SSD) | ~12 |
| Storage Account | Standard LRS | ~1（按用量） |
| Azure OpenAI | 复用现有 yiqxie-ai | 按调用计费 |
| **合计** | | **≈ 26 USD + AI 调用费** |

---

## 🔐 Microsoft Entra ID 配置

> 本节只在需要登录保护时执行；MVP 模式可在后端把 `AUTH_ENABLED=false` 关闭。

### 1. 创建后端 API 应用注册

```powershell
# 创建 API 应用
$apiAppId = az ad app create --display-name "ppt-agent-api" --query appId -o tsv

# 暴露 access_as_user 权限
az ad app update --id $apiAppId --identifier-uris "api://$apiAppId"

# 通过 Portal 添加 OAuth2 Permission "access_as_user"（CLI 操作 Pre-Authorized 较繁琐）
```

### 2. 创建前端 SPA 应用注册

```powershell
$spaAppId = az ad app create `
  --display-name "ppt-agent-spa" `
  --spa-redirect-uris "https://<webAppName>.azurewebsites.net" "http://localhost:5173" `
  --query appId -o tsv

# 给 SPA 添加对 API 的委派权限
az ad app permission add --id $spaAppId `
  --api $apiAppId `
  --api-permissions "<access_as_user-perm-id>=Scope"
```

### 3. 配置后端环境变量

```
AUTH_ENABLED=true
AAD_TENANT_ID=<tenant-id>
AAD_API_AUDIENCE=api://<apiAppId>
AAD_REQUIRED_SCOPE=access_as_user
```

### 4. 配置前端环境变量

```
VITE_AUTH_ENABLED=true
VITE_AAD_TENANT_ID=<tenant-id>
VITE_AAD_CLIENT_ID=<spaAppId>
VITE_AAD_API_SCOPE=api://<apiAppId>/access_as_user
```

---

## 📡 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET`   | `/healthz` | 健康检查 |
| `GET`   | `/api/config` | 公共配置（前端启动时调用）|
| `POST`  | `/api/jobs/upload` | 上传 PPT（multipart）|
| `GET`   | `/api/jobs` | 列出 Job（支持 status/skip/limit）|
| `GET`   | `/api/jobs/{id}` | 查询单个 Job |
| `POST`  | `/api/jobs/{id}/start` | 重新触发处理 |
| `DELETE`| `/api/jobs/{id}` | 删除 Job 及其全部 slide 与 blob |
| `GET`   | `/api/slides` | 列出 slide（支持 keyword/tag/job_id 过滤）|
| `GET`   | `/api/slides/{id}` | 查询 slide 详情 |
| `PUT`   | `/api/slides/{id}` | 更新 prompt / tag / 标题 / 摘要 |
| `POST`  | `/api/slides/batch-delete` | 批量删除 slide |
| `GET`   | `/api/slides/tags/all` | 列出所有出现过的 tag |
| `WS`    | `/ws/progress?job_id=...` | 实时进度（不带 job_id 则订阅所有）|

完整 OpenAPI 文档：`https://<host>/api/docs`。

---

## 💡 关键技术决策

| 决策 | 取舍 |
|---|---|
| **PPT 渲染**：LibreOffice headless | 跨平台、免费、保真度可接受；放弃了纯 Python 渲染（python-pptx 不能真渲染） |
| **AI 模型**：Azure OpenAI GPT-4o | 多模态视觉能力强、中文好；可通过 `AZURE_OPENAI_VISION_DEPLOYMENT` 切换 `gpt-4.5-preview` 等 |
| **进度推送**：WebSocket | 双向、低延迟、原生支持；前端带自动重连与心跳 |
| **数据库**：PostgreSQL + JSONB | tag/style 用 JSON 存储，检索通过 `jsonb_array_elements_text` |
| **鉴权**：MSAL + JWT | 标准 Entra ID；后端不自维护用户表 |
| **部署**：单镜像 + App Service | 简单、低成本；FastAPI 同时托管前端 dist |

---

## 🛠 开发与扩展

- **添加新分析维度**：修改 [ai.py](backend/app/services/ai.py) 中 `_SYSTEM_PROMPT`，并在 [models.py](backend/app/models/models.py) 的 `style_meta` 中保存。
- **支持更多文件类型**（如 Keynote/PDF）：在 [ppt_renderer.py](backend/app/services/ppt_renderer.py) 加分支。
- **接入向量检索**：在 `Slide` 表上增加 embedding 列（pgvector），在 `orchestrator.py` 写入时同步生成。
- **CI/CD**：默认 [.github/workflows/build.yml](.github/workflows/build.yml) 已构建推送到 GHCR；可加一个 deploy job 自动 `az webapp config container set`。

---

## 📜 License

MIT © yiqxie
