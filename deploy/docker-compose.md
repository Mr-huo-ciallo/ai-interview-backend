# Docker Compose 部署

在项目根目录执行：

```bash
cp .env.docker.example .env
# 编辑 .env，设置 MySQL 密码和 AUTH_SECRET
docker compose up -d --build
```

首次启动会等待 MySQL 健康检查，并在后端启动前自动执行 `alembic upgrade head`。前端入口为 `http://localhost:8080`，后端健康检查可通过 `http://localhost:8080/backend-health` 访问。

查看状态和日志：

```bash
docker compose ps
docker compose logs -f backend
```

停止服务但保留数据库卷：

```bash
docker compose down
```
