from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

import auth_utils
import llm_client
from models import UserLlmConfigModel


logger = logging.getLogger(__name__)

ALLOWED_API_FORMATS = {"openai", "anthropic"}

LLM_PROVIDER_PRESETS = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "badge": "高性价比",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://api.deepseek.com/v1",
        "defaultModel": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "requiresApiKey": True,
        "description": "DeepSeek 官方 API，原生兼容 OpenAI Chat Completions。",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "badge": "主流",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://api.openai.com/v1",
        "defaultModel": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        "requiresApiKey": True,
        "description": "OpenAI 官方接口，支持 GPT-4o / GPT-4.1 系列模型。",
    },
    {
        "id": "qwen",
        "name": "通义千问（阿里云百炼）",
        "badge": "国内直连",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "defaultModel": "qwen-plus",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen2.5-72b-instruct"],
        "requiresApiKey": True,
        "description": "阿里云百炼 OpenAI 兼容模式接口，国内访问稳定。",
    },
    {
        "id": "zhipu",
        "name": "智谱 AI（GLM）",
        "badge": "国内直连",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://open.bigmodel.cn/api/paas/v4",
        "defaultModel": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4-air", "glm-4-plus"],
        "requiresApiKey": True,
        "description": "智谱开放平台接口，支持 GLM-4 系列模型。",
    },
    {
        "id": "moonshot",
        "name": "Moonshot（Kimi）",
        "badge": "长文本",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://api.moonshot.cn/v1",
        "defaultModel": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "kimi-k2-0711-preview"],
        "requiresApiKey": True,
        "description": "月之暗面 Kimi 开放平台，适合长简历与深度复盘。",
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "badge": "主流",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://generativelanguage.googleapis.com/v1beta/openai",
        "defaultModel": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        "requiresApiKey": True,
        "description": "Google Gemini OpenAI 兼容端点。",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "badge": "原生协议",
        "apiFormat": "anthropic",
        "defaultBaseUrl": "https://api.anthropic.com/v1",
        "defaultModel": "claude-3-5-sonnet-latest",
        "models": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-sonnet-4-20250514"],
        "requiresApiKey": True,
        "description": "Anthropic 官方 Messages API（使用 x-api-key 认证）。",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "badge": "聚合",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://openrouter.ai/api/v1",
        "defaultModel": "openai/gpt-4o-mini",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat"],
        "requiresApiKey": True,
        "description": "多模型聚合路由，一个 Key 调用各家主流模型。",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动（SiliconFlow）",
        "badge": "开源模型",
        "apiFormat": "openai",
        "defaultBaseUrl": "https://api.siliconflow.cn/v1",
        "defaultModel": "deepseek-ai/DeepSeek-V3",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct", "THUDM/glm-4-9b-chat"],
        "requiresApiKey": True,
        "description": "国内开源模型托管平台，OpenAI 兼容接口。",
    },
    {
        "id": "custom",
        "name": "自定义 API",
        "badge": "灵活扩展",
        "apiFormat": "openai",
        "defaultBaseUrl": "",
        "defaultModel": "",
        "models": [],
        "requiresApiKey": False,
        "description": "支持 OneAPI / NewAPI / Ollama（如 http://localhost:11434/v1）/ vLLM 或任意私有代理。",
    },
]

PROVIDER_IDS = {item["id"] for item in LLM_PROVIDER_PRESETS}


def _get_fernet() -> Fernet:
    digest = hashlib.sha256(auth_utils.AUTH_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(raw_key: str) -> str:
    if not raw_key:
        return ""
    return _get_fernet().encrypt(raw_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    try:
        return _get_fernet().decrypt(encrypted_key.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("用户 LLM API Key 解密失败，可能因为 AUTH_SECRET 已变更")
        return ""


def mask_api_key(raw_key: str) -> str:
    key = (raw_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}****{key[-4:]}"


def _is_private_url_blocking_enabled() -> bool:
    explicit = os.getenv("LLM_BLOCK_PRIVATE_URLS", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    return os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}


def _allowed_private_hosts() -> set[str]:
    raw = os.getenv("LLM_ALLOWED_PRIVATE_HOSTS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_non_public_ip(ip_obj) -> bool:
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _check_host_ssrf(hostname: str) -> None:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        raise HTTPException(status_code=400, detail="API Base URL 缺少有效主机名")

    # 始终拦截云元数据服务主机名
    if host in {"metadata.google.internal", "metadata"}:
        raise HTTPException(status_code=400, detail="禁止使用云元数据地址作为 API Base URL")

    allowed_hosts = _allowed_private_hosts()
    if host in allowed_hosts:
        return

    block_private = _is_private_url_blocking_enabled()
    if block_private and (host == "localhost" or host.endswith(".local") or host.endswith(".internal")):
        raise HTTPException(status_code=400, detail="生产环境禁止使用内网或本机地址，如需放行请配置 LLM_ALLOWED_PRIVATE_HOSTS")

    # 检查 IP 字面量
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if ip_obj.is_link_local:
            raise HTTPException(status_code=400, detail="禁止使用链路本地或云元数据地址作为 API Base URL")
        if block_private and _is_non_public_ip(ip_obj):
            raise HTTPException(status_code=400, detail="生产环境禁止使用内网或回环地址，如需放行请配置 LLM_ALLOWED_PRIVATE_HOSTS")
        return

    if not block_private:
        return

    # 生产环境解析 DNS，拦截指向内网或云元数据的域名
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return

    for info in addr_infos:
        resolved_ip = info[4][0]
        try:
            resolved_obj = ipaddress.ip_address(resolved_ip)
        except ValueError:
            continue
        if _is_non_public_ip(resolved_obj):
            raise HTTPException(status_code=400, detail="生产环境禁止访问解析到内网或保留地址的域名")


def _validate_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise HTTPException(status_code=400, detail="API Base URL 格式无效，必须以 http:// 或 https:// 开头")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="API Base URL 不允许包含认证信息")
    _check_host_ssrf(parsed.hostname)
    return cleaned


def _validate_common_fields(provider: str, api_format: str, base_url: str, model: str) -> tuple[str, str, str, str]:
    normalized_provider = (provider or "custom").strip().lower()
    if normalized_provider not in PROVIDER_IDS:
        normalized_provider = "custom"

    normalized_format = (api_format or "openai").strip().lower()
    if normalized_format not in ALLOWED_API_FORMATS:
        raise HTTPException(status_code=400, detail="不支持的 API 协议格式，仅支持 openai 或 anthropic")

    cleaned_url = _validate_base_url(base_url)
    cleaned_model = (model or "").strip()
    if not cleaned_model:
        raise HTTPException(status_code=400, detail="请填写模型名称")

    return normalized_provider, normalized_format, cleaned_url, cleaned_model


def _serialize_config(record: UserLlmConfigModel | None) -> dict | None:
    if not record:
        return None
    decrypted = decrypt_api_key(record.api_key_encrypted or "")
    return {
        "provider": record.provider,
        "apiFormat": record.api_format,
        "baseUrl": record.base_url,
        "model": record.model,
        "enabled": bool(record.enabled),
        "hasApiKey": bool(decrypted),
        "apiKeyMasked": mask_api_key(decrypted),
        "updatedAt": record.updated_at.strftime("%Y-%m-%d %H:%M:%S") if record.updated_at else "",
    }


def get_user_llm_config_record(db: Session, user_id: int) -> UserLlmConfigModel | None:
    return (
        db.query(UserLlmConfigModel)
        .filter(UserLlmConfigModel.user_id == user_id)
        .first()
    )


def get_user_active_llm_runtime_config(db: Session, user_id: int) -> dict | None:
    record = get_user_llm_config_record(db, user_id)
    if not record or not record.enabled:
        return None
    api_key = decrypt_api_key(record.api_key_encrypted or "")
    if record.provider != "custom" and not api_key:
        return None
    return {
        "provider": record.provider,
        "api_format": record.api_format or "openai",
        "base_url": record.base_url,
        "model": record.model,
        "api_key": api_key,
        "source": "user",
    }


def get_llm_settings_payload(db: Session, user_id: int) -> dict:
    record = get_user_llm_config_record(db, user_id)
    serialized = _serialize_config(record)
    system_available = llm_client.is_system_llm_configured()

    if serialized and serialized["enabled"] and (serialized["provider"] == "custom" or serialized["hasApiKey"]):
        effective_source = "user"
    elif system_available:
        effective_source = "system"
    else:
        effective_source = "none"

    return {
        "config": serialized,
        "systemDefaultAvailable": system_available,
        "effectiveSource": effective_source,
    }


def upsert_user_llm_config(db: Session, user_id: int, data: dict) -> dict:
    provider, api_format, base_url, model = _validate_common_fields(
        data.get("provider", "custom"),
        data.get("apiFormat", "openai"),
        data.get("baseUrl", ""),
        data.get("model", ""),
    )
    enabled = bool(data.get("enabled", True))
    incoming_key = (data.get("apiKey") or "").strip()

    record = get_user_llm_config_record(db, user_id)
    existing_key = decrypt_api_key(record.api_key_encrypted) if record else ""
    final_key = incoming_key or existing_key

    if provider != "custom" and not final_key:
        raise HTTPException(status_code=400, detail="请填写 API Key")

    encrypted_key = encrypt_api_key(final_key) if final_key else ""

    if record:
        record.provider = provider
        record.api_format = api_format
        record.base_url = base_url
        record.model = model
        record.api_key_encrypted = encrypted_key
        record.enabled = enabled
    else:
        record = UserLlmConfigModel(
            user_id=user_id,
            provider=provider,
            api_format=api_format,
            base_url=base_url,
            model=model,
            api_key_encrypted=encrypted_key,
            enabled=enabled,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return get_llm_settings_payload(db, user_id)


def delete_user_llm_config(db: Session, user_id: int) -> dict:
    record = get_user_llm_config_record(db, user_id)
    if record:
        db.delete(record)
        db.commit()
    return get_llm_settings_payload(db, user_id)


def test_user_llm_config(db: Session, user_id: int, data: dict) -> dict:
    provider, api_format, base_url, model = _validate_common_fields(
        data.get("provider", "custom"),
        data.get("apiFormat", "openai"),
        data.get("baseUrl", ""),
        data.get("model", ""),
    )
    incoming_key = (data.get("apiKey") or "").strip()
    if not incoming_key:
        record = get_user_llm_config_record(db, user_id)
        incoming_key = decrypt_api_key(record.api_key_encrypted) if record else ""

    if provider != "custom" and not incoming_key:
        raise HTTPException(status_code=400, detail="请填写 API Key 后再测试连接")

    runtime_config = {
        "provider": provider,
        "api_format": api_format,
        "base_url": base_url,
        "model": model,
        "api_key": incoming_key,
        "source": "test",
    }
    return llm_client.test_llm_connection(runtime_config)
