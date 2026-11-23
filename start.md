# 开发任务接手

从本地 `vue-projects` 工作区开始。前端和后端各有独立的 Git 历史。续接任务时，先看上一轮交接中的提交、未验证项和下一步，再核对当前分支与工作区改动。

```powershell
git -C ai-interview-platform status --short --branch
git -C ai-interview-backend status --short --branch
```

## 按任务找到入口

| 改动范围 | 从哪里开始 |
| --- | --- |
| 网页、桌面端、浏览器扩展 | [项目 README](../ai-interview-platform/README.md) 列有业务流程、代码目录和各端入口 |
| 前后端联调 | 从前端 `src/api/` 中的请求路径查到后端 `main.py` 或 `routers/` 中的处理函数，核对请求和响应字段 |
| 数据库或后端运行环境 | [后端环境说明](ENVIRONMENTS.md) 说明虚拟环境选择、数据库配置和迁移流程 |
| 服务器部署 | [Docker Compose 部署文档](deploy/docker-compose.md) 记录服务器目录和部署命令 |

## 本地运行网页与 API

以下命令适用于已配置开发依赖和本地数据库的 Windows 环境。首次配置数据库或模型变更后，先按后端环境说明核对开发库并完成迁移。

从工作区根目录打开两个 PowerShell 终端。第一个启动 API，默认地址为 `http://127.0.0.1:8000`。

```powershell
cd ai-interview-backend
.\start_backend.ps1 -EnvName auto -Reload
```

第二个启动网页，打开 Vite 输出的本地地址。联调时核对 `VITE_API_BASE_URL` 是否指向上面的 API，配置示例见[前端开发环境样例](../ai-interview-platform/.env.development.example)。

```powershell
cd ai-interview-platform
npm run dev
```

开始修改前，把验收条件写成一个可观察结果，例如“保存编辑后的 JD，刷新后仍显示新内容”。收尾时按 [end.md](end.md) 验证同一条路径。
