# Docker Compose 部署

本文件是 Docker 部署的权威入口。Compose 位于后端仓库根目录，并同时构建后端、前端和 MySQL。不要再用 `deploy/one_click_deploy.sh` 安装宿主机版 Python、Node、MySQL 服务。

## 目录要求

服务器上两个 GitHub 仓库必须处于同一级目录：

```text
/opt/stacks/ai-interview/
├── ai-interview-backend/
└── ai-interview-platform/
```

Compose 只发布前端端口。浏览器的 `/api/*` 请求由前端 Nginx 转发给内部后端；后端和 MySQL 不向宿主机发布端口。

## 首次启动

```bash
cd /opt/stacks/ai-interview
git clone https://github.com/Mr-huo-ciallo/ai-interview-backend.git
git clone https://github.com/Mr-huo-ciallo/ai-interview-platform.git
cd ai-interview-backend
cp .env.docker.example .env
```

编辑 `.env`。至少替换 `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`AUTH_SECRET`；要使用 AI 功能，还需要填写三项 `LLM_*`。密码建议使用纯十六进制，避免数据库 URL 转义问题：

```bash
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 32
```

检查最终配置后启动：

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

首次启动流程为：MySQL 健康检查通过 → `migrate` 执行 `alembic upgrade head` → 后端就绪 → 前端启动。默认仅监听宿主机 `127.0.0.1:8080`：

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/backend-health
```

如果暂时只通过 Tailscale 访问，可将 `APP_BIND_ADDRESS` 设置为服务器的 Tailscale 地址。准备域名和 HTTPS 时，保持 `127.0.0.1`，由宿主机反向代理转发到 8080。

## 更新与回滚

当前服务器已部署在 `/home/mr_huo/ai-interview-backend`，前端仓库位于同级目录 `/home/mr_huo/ai-interview-platform`。以下命令在后端目录执行。

更新前先备份数据库，再分别拉取两个仓库的目标提交：

```bash
docker compose exec -T database sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' > ai_interview_$(date +%Y%m%d_%H%M%S).sql
git pull --ff-only
git -C ../ai-interview-platform pull --ff-only
docker compose build
docker compose up -d
docker compose ps
```

产品经理首批题位于 `seed/product_manager_questions.json`，共 30 题。更新后先预览缺口，再导入；命令只补不存在的题，不覆盖后台已编辑的内容：

```bash
docker compose run --rm --no-deps backend python -m seed.product_manager
docker compose run --rm --no-deps backend python -m seed.product_manager --apply
docker compose exec -T database sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -N -e "SELECT role, COUNT(*) FROM interview_questions WHERE role = '\''product_manager'\'' GROUP BY role;"'
```

题目措辞、参考回答和追问为项目原创；`sources` 记录设计依据，不表示从这些网站复制题目。评分维度采用现有数据库字段，产品经理的 `techScore` 在界面显示为“产品判断”。
目前校准仅验证产品术语与强弱回答排序；尚未用人工标注答卷核对绝对分数。

镜像标签由 `.env` 中的 `APP_IMAGE_TAG` 控制。正式部署时应改成 Git 提交短 SHA，而不是长期使用 `local` 或 `latest`。回滚时切回两个仓库的已知提交，恢复对应数据库备份，再重新构建。

查看日志：

```bash
docker compose logs --tail=200
docker compose logs -f backend
```

停止服务但保留数据库卷：

```bash
docker compose down
```

不要执行 `docker compose down -v`，除非已经确认要删除 MySQL 数据卷。

## 容器化之后仍需准备

1. 在服务器确认 Docker Engine、Compose v2、剩余内存和磁盘空间；数据库卷优先放 SSD，备份放机械盘。
2. 决定访问入口：仅 Tailscale、局域网，或域名加 HTTPS。只有最后一种需要公网 DNS、80/443 端口和 TLS 证书。
3. 从当前 MySQL 导出数据，并在测试环境实际完成一次导入与回滚，不能只保存备份文件。
4. 将 `.env` 仅保留在服务器，设置限制性权限，不提交 API Key、数据库密码和 `AUTH_SECRET`。
5. 配置数据库定时备份、Docker 日志轮转、磁盘空间告警和容器健康状态检查。
6. 发布前执行后端测试、`alembic check`、前端构建和一次完整的注册—面试—报告—求职仓冒烟测试。
7. 稳定后再增加 GitHub Actions：测试、构建固定提交镜像、推送镜像仓库、服务器拉取并重建。首轮部署不依赖自动发布。
