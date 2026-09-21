# Python 虚拟环境说明

本项目当前存在两个 Python 虚拟环境：

| 位置 | 用途建议 | 当前说明 |
| --- | --- | --- |
| `../.venv` | 项目根目录通用环境 | 当前依赖较完整，包含 FastAPI、SQLAlchemy、PyMySQL、HTTPX 等后端运行依赖 |
| `.venv` | 后端专用环境 | 建议作为后端长期使用环境；如果缺依赖，请执行 `pip install -r requirements.txt` |

## 推荐做法

部署和长期开发建议优先使用后端专用环境：

```powershell
cd ai-interview-backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start_backend.ps1 -EnvName backend -Reload
```

如果后端专用环境暂时缺少依赖，也可以让启动脚本自动选择可用环境：

```powershell
cd ai-interview-backend
.\start_backend.ps1 -EnvName auto -Reload
```

`auto` 模式会优先检查 `ai-interview-backend/.venv`，如果该环境缺少依赖，则回退到项目根目录 `.venv`。

## 生产部署建议

线上服务器建议只保留一个后端专用虚拟环境，避免多环境依赖不一致：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux 服务器可使用：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## 环境变量

真实配置不要写入 Git。复制 `.env.example` 为 `.env` 后填写：

```env
DATABASE_URL=mysql+pymysql://ai_interview_user:your_password@127.0.0.1:3306/ai_interview
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://your-domain.com
AUTH_SECRET=replace_with_a_long_random_value_and_keep_it_stable
AUTH_TOKEN_TTL_SECONDS=604800
LLM_API_KEY=your_key
LLM_BASE_URL=https://your-llm-base-url/v1
LLM_MODEL=your_model
```

## 数据库迁移

项目已使用 Alembic 管理数据库版本。新环境建库或部署时执行：

```powershell
cd ai-interview-backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

已有数据库如果此前由 `Base.metadata.create_all` 创建，先备份并将表结构校准到初始迁移，再将其标记为当前初始版本，避免重复建表。不得在结构尚未一致时直接执行 `stamp`：

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini stamp head
```

应用启动不再自动建表；所有环境均应在启动应用前执行 `upgrade head`。后续修改模型时，应先创建新的迁移版本，再部署代码：

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini revision --autogenerate -m "describe_change"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

提交前运行只读结构检查，确认 ORM 模型没有遗漏迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```
