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
cd /opt/ai-interview/ai-interview-backend
./.venv/bin/python scripts/import_questions.py
```

导入逻辑：

- 如果服务器数据库中已存在相同 `role + content` 的题目，则更新该题目。
- 如果不存在，则新增题目。

## 注意

执行脚本前请确认 `.env` 中的 `DATABASE_URL` 指向目标数据库。
