import os


APP_ENV = os.getenv("APP_ENV", "development").lower()


def validate_runtime_config():
    if APP_ENV not in {"production", "prod"}:
        return

    required_names = ["DATABASE_URL", "AUTH_SECRET"]
    missing_names = [name for name in required_names if not os.getenv(name)]
    if missing_names:
        raise RuntimeError(f"生产环境缺少必要配置：{', '.join(missing_names)}")
