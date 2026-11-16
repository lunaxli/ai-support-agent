# AI Support Agent

**AI 驱动的企业智能客服与工单管理系统**

AI Support Agent 面向企业客服工单处理场景，集成工单管理、智能分类、知识库检索、AI 回复草稿和人工审核。系统通过 LangGraph 编排工单处理流程，使用 DeepSeek 生成结构化分析与回复建议，并由客服审核后将最终结果反馈至工单详情。

项目提供 React 管理界面和 FastAPI 接口，支持 PostgreSQL 数据持久化、JWT 身份认证、角色权限、操作记录以及 Docker Compose 本地运行。

## 功能特性

- **工单管理**：创建、查询、编辑、删除工单，按状态筛选和分页；记录处理状态及时间。
- **多角色权限**：基于 JWT 身份认证，区分客户、客服和管理员；客户仅能访问自己的工单，客服具有分析与审核权限。
- **智能分类**：调用 DeepSeek 对工单进行类别识别、优先级判断和问题摘要生成。
- **Agent 工作流**：使用 LangGraph 将分类、风险识别、知识库检索、草稿生成和人工处理编排成条件工作流。
- **知识库检索**：从 Markdown 知识库提取片段，使用 BM25 关键词匹配获取相关内容，并记录引用来源。
- **人工审核**：高风险、检索无结果或模型异常的工单进入人工处理分支；支持批准或驳回回复草稿。
- **可追溯记录**：保存 AI 分析结果、引用片段、审核决定和操作日志，支持查看历史处理过程。
- **双模式运行**：支持 DeepSeek 真实 API 模式和无需模型密钥的 Mock 演示模式。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、Tailwind CSS、shadcn/ui |
| 后端 | Python 3.14、FastAPI、Pydantic、SQLModel |
| 数据库 | PostgreSQL、Alembic |
| AI 应用 | DeepSeek API、LangGraph、BM25 |
| 鉴权与安全 | JWT、角色权限、用户数据隔离 |
| 工程化 | Docker Compose、uv、Bun、pytest、Playwright、GitHub Actions |

## 系统架构

```mermaid
flowchart TD
    U[客户提交工单] --> API[React + FastAPI]
    API --> DB[(PostgreSQL)]
    API --> C[LangGraph: 工单分类与风险识别]
    C -->|正常请求| K[BM25 知识库检索]
    C -->|高风险 / 模型异常| H[人工处理]
    K -->|有相关内容| D[DeepSeek 生成回复草稿]
    K -->|无相关内容| H
    D -->|草稿与引用有效| R[客服审核]
    D -->|草稿或引用无效| H
    H --> R
    R -->|批准| F[保存最终回复 · 工单已解决]
    R -->|驳回| B[返回处理中 · 可重新分析]
    F --> DB
    B --> DB
```

> 检索模块当前采用 **BM25 关键词检索**，不是向量数据库检索。系统校验引用 ID 是否属于当前检索结果，但最终回复仍需人工核对内容准确性。

## 快速启动（Docker）

### 1. 环境准备

- Docker Desktop 或支持 Docker Compose v2 的 Docker 环境
- 用于配置的项目根目录 `.env` 文件
- 使用真实模型时，需要可用的 DeepSeek API Key

### 2. 配置环境变量

在项目根目录创建 `.env`，填写以下配置。**如果已有能正常运行的 `.env`，请保留原文件，不要覆盖。**

```dotenv
PROJECT_NAME="AI Support Agent"
SECRET_KEY=replace_with_a_long_random_secret
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=replace_with_a_secure_admin_password
POSTGRES_PASSWORD=replace_with_a_secure_database_password
DATABASE_URL=postgresql://postgres:replace_with_a_secure_database_password@localhost:5432/app
FRONTEND_HOST=http://localhost:8000

AI_MODE=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

说明：

- `AI_MODE=deepseek` 启用真实模型。无 API Key 演示时可改为 `AI_MODE=mock`，并留空 `DEEPSEEK_API_KEY`。
- `DATABASE_URL` 中的密码应与 `POSTGRES_PASSWORD` 一致；本地 Compose 会使用内部数据库地址连接 PostgreSQL。
- 已经初始化过 PostgreSQL 数据卷的项目，**不要直接更改数据库密码**，否则可能导致连接失败。
- `.env` 含有敏感信息，必须保持在 Git 忽略范围内，切勿提交到公开仓库。
- 本配置面向本地开发与演示，**不是可直接用于公网的生产配置**。

### 3. 启动服务

在项目根目录运行：

```powershell
docker compose -f compose.demo.yml config --quiet
docker compose -f compose.demo.yml up --build -d --wait
```

启动完成后访问：

- **系统前端**：http://localhost:8000
- **FastAPI 接口文档**：http://localhost:8000/docs

后端启动时执行数据库迁移及初始管理员初始化。使用 `.env` 中配置的 `FIRST_SUPERUSER` 和 `FIRST_SUPERUSER_PASSWORD` 登录。

### 4. 创建演示用户（可选）

可以创建一个客户账号与一个客服账号，用于测试不同角色的完整流程：

```powershell
docker compose -f compose.demo.yml exec -e FASTAPI_ENV=development backend python -m app.support.demo --password YourDemoPassword123
```

该命令会创建以下账号（若账号已存在则跳过）：

| 角色 | 邮箱 | 密码 |
| --- | --- | --- |
| 客户 | `customer@example.com` | 上述命令中设置的密码 |
| 客服 | `agent@example.com` | 上述命令中设置的密码 |


## 功能演示

推荐分别使用浏览器普通窗口和无痕窗口，以避免不同账号共享登录状态。

1. **客户提交工单**：客户登录，进入「工单中心」，创建标题为「无法登录账户」的工单，描述填写「忘记密码，登录时提示密码错误，如何重置？」。
2. **客服分析工单**：客服登录，打开刚提交的工单，点击「运行 AI 分析」。系统生成类别、优先级和问题摘要。
3. **查看知识库依据**：查看分析记录中的回复草稿及 `account.md` 等知识库引用片段，并人工核对内容。
4. **人工审核**：客服填写处理备注，选择批准或驳回回复草稿。批准后工单进入「已解决」。
5. **客户查看回复**：客户刷新工单详情，查看保存的最终回复。

还可以使用「重复扣款申请退款」测试高风险人工处理分支，使用「蓝牙温度标签配置」测试无知识库证据时的人工处理分支。

## 项目结构

```text
ai-support-agent/
├── backend/
│   ├── app/
│   │   ├── api/routes/support.py       # 工单接口、权限与业务操作
│   │   ├── support/
│   │   │   ├── ai_schemas.py            # AI 结构化输出模型
│   │   │   ├── models.py                # 工单、分析、审核与日志模型
│   │   │   ├── providers.py             # DeepSeek / Mock 适配器
│   │   │   ├── knowledge.py             # BM25 知识库检索
│   │   │   ├── workflow.py              # LangGraph 工作流
│   │   │   └── kb/                      # 示例知识库
│   │   └── alembic/                     # 数据库迁移
│   └── tests/                            # 后端自动化测试
├── frontend/
│   ├── src/routes/_layout/tickets.tsx   # React 工单工作台
│   └── tests/support.spec.ts            # 前端端到端测试
├── compose.demo.yml                     # 本地演示容器编排
├── compose.yml                          # 开发服务编排
├── docs/
│   ├── architecture.md                   # 详细架构设计
│   └── verification.md                   # 测试验证记录
└── README.md
```

## 测试与排障

项目包含：

- **pytest**：接口、权限隔离、状态流转、并发版本控制、AI 工作流分支等测试。
- **Playwright**：登录、工单提交、客服分析、人工审核、跨账号查看结果等浏览器端到端测试。
- **GitHub Actions**：后端、前端和 Docker Compose 相关自动化流程。

有关测试环境与历史执行记录，见 [验证记录](docs/verification.md)；完整本地开发方式见 [开发指南](development.md)。测试记录不应代替在当前环境重新运行验证。

查看服务状态：

```powershell
docker compose -f compose.demo.yml ps
```

查看后端日志：

```powershell
docker compose -f compose.demo.yml logs --tail=100 backend
```

停止服务（保留数据库卷）：

```powershell
docker compose -f compose.demo.yml down
```
