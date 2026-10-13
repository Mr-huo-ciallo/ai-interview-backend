# 数据迁移脚本

这些脚本用于把本地题库迁移到云服务器数据库。

## 导出本地题库

在本地后端目录执行：

```powershell
cd D:\++Dev-Cpp\Mr.huo\vue-projects\ai-interview-backend
.\.venv\Scripts\python.exe scripts\export_questions.py
```

导出文件：

```text
data/interview_questions_export.json
```

## 导入服务器题库

将 `data/interview_questions_export.json` 上传到服务器后端项目的 `data/` 目录，然后执行：

```bash
cd /home/mr_huo/ai-interview-backend
./.venv/bin/python scripts/import_questions.py
```

导入逻辑：

- 如果服务器数据库中已存在相同 `role + content` 的题目，则更新该题目。
- 如果不存在，则新增题目。

## 注意

执行脚本前请确认 `.env` 中的 `DATABASE_URL` 指向目标数据库。

## 服务器数据库定时备份

服务器上的 `scripts/backup_database.sh` 使用 Docker Compose 的 `database` 服务，将整个 `MYSQL_DATABASE` 导出为压缩 SQL。默认保存到 `/home/mr_huo/backups/ai-interview/`，仅备份成功后清理超过 30 天的本脚本备份。该目录位于服务器本机，不是异机灾备。

服务器用户 `mr_huo` 的 crontab 每天 03:00（服务器时区 Asia/Shanghai）运行：

```cron
0 3 * * * /home/mr_huo/ai-interview-backend/scripts/backup_database.sh >> /home/mr_huo/backups/ai-interview/backup.log 2>&1
```

手动执行与检查：

```bash
cd /home/mr_huo/ai-interview-backend
./scripts/backup_database.sh
crontab -l
ls -lh /home/mr_huo/backups/ai-interview/
tail -n 20 /home/mr_huo/backups/ai-interview/backup.log
```

恢复前先确认目标数据库并另外备份当前状态；不要将备份直接导回仍在使用的生产数据库。备份文件可先用 `gzip -t` 和对应 `.sha256` 校验，再在独立 MySQL 实例试恢复。
