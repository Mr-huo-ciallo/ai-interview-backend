import os


APP_ENV = os.getenv("APP_ENV", "development").lower()
AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes"}


def validate_runtime_config():
    if APP_ENV not in {"production", "prod"}:
        return

    required_names = ["DATABASE_URL", "AUTH_SECRET"]
    missing_names = [name for name in required_names if not os.getenv(name)]
    if missing_names:
        raise RuntimeError(f"生产环境缺少必要配置：{', '.join(missing_names)}")

    if AUTO_CREATE_TABLES:
        raise RuntimeError("生产环境必须设置 AUTO_CREATE_TABLES=false，并通过 Alembic 执行数据库迁移")
