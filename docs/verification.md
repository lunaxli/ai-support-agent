# 本地验证记录

验证环境为 Windows、Python 3.14、Bun 1.4.4、Docker Compose 和 PostgreSQL 18。测试使用示例数据。

| 项目 | 结果 |
| --- | --- |
| 从锁文件安装依赖 | 后端 `uv` 和前端 Bun 安装完成 |
| PostgreSQL 迁移 | 空数据库执行 `alembic upgrade head`，再执行 `alembic check`，无待生成迁移 |
| 完整后端 pytest | 65 项通过，包含上游测试以及工单 CRUD、角色授权、客户隔离、并发版本冲突、风险和无证据分流 |
| TypeScript 与 Vite | 生产构建通过 |
| Docker Compose | 从源码构建并启动，PostgreSQL 与应用容器均达到健康状态，从容器创建演示用户 |
| Compose HTTP 工单流程 | 客户与客服分别登录，验证带引用草稿获批、风险人工回复获批、无证据驳回三条分支 |
| Compose 浏览器流程 | Chromium 上 12 项通过，含登录、退出、引用审核、客服权限与跨账号展示最终回复 |
| 完整 Playwright 套件 | 使用本地 FastAPI 服务、独立 PostgreSQL 测试库和 Mailpit，64 项通过，含上游用户管理、密码重置和工单用例 |
| ZIP 解压启动 | 在独立项目名下从解压源码构建，初始化新 PostgreSQL 数据卷，验证首页、管理员 JWT 登录和 Mock 模式 |
| DeepSeek 适配器 | 使用模拟 HTTP 响应验证 OpenAI 兼容请求、JSON 校验、证据引用和错误转人工 |

尚未执行真实 DeepSeek API 调用，默认 Mock 演示无需密钥。GitHub Actions 配置保留在仓库中，本记录为本地结果。

