"""Microsoft Entra ID JWT Bearer Token 校验。

通过获取租户 JWKS 公钥来验证前端传来的 access token，
确保只有合法的 Entra ID 用户才能访问受保护的 API。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

# 如果不启用认证，则使用 auto_error=False，方便测试
_bearer_scheme = HTTPBearer(auto_error=False)

# JWKS 缓存（避免每次请求都拉取公钥）
_JWKS_CACHE: Dict[str, Any] = {"data": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600  # 1 小时


async def _get_jwks(tenant_id: str) -> Dict[str, Any]:
    """获取 Entra ID 的 JWKS 公钥集合，带 1 小时缓存。"""
    now = time.time()
    if (
        _JWKS_CACHE["data"] is not None
        and now - _JWKS_CACHE["fetched_at"] < _JWKS_TTL_SECONDS
    ):
        return _JWKS_CACHE["data"]

    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    _JWKS_CACHE["data"] = data
    _JWKS_CACHE["fetched_at"] = now
    return data


def _find_signing_key(jwks: Dict[str, Any], kid: str) -> Optional[Dict[str, Any]]:
    """根据 kid 在 JWKS 中查找对应的公钥。"""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_access_token(token: str, settings: Settings) -> Dict[str, Any]:
    """校验 JWT 并返回解码后的 payload。

    校验项：签名、issuer、audience、scope。
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="无法解析 token 头部") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="token 缺少 kid")

    jwks = await _get_jwks(settings.aad_tenant_id)
    key_data = _find_signing_key(jwks, kid)
    if key_data is None:
        # 公钥可能轮换，强制刷新一次再试
        _JWKS_CACHE["data"] = None
        jwks = await _get_jwks(settings.aad_tenant_id)
        key_data = _find_signing_key(jwks, kid)
    if key_data is None:
        raise HTTPException(status_code=401, detail="未找到匹配的签名公钥")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
    issuer = f"https://login.microsoftonline.com/{settings.aad_tenant_id}/v2.0"
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[unverified_header.get("alg", "RS256")],
            audience=settings.aad_api_audience,
            issuer=issuer,
            options={"require": ["exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="token 已过期") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(status_code=401, detail="audience 不匹配") from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(status_code=401, detail="issuer 不匹配") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"token 校验失败：{exc}") from exc

    # 校验 scope（v2.0 token 中权限保存在 "scp" 字段）
    if settings.aad_required_scope:
        scopes = (payload.get("scp") or "").split()
        if settings.aad_required_scope not in scopes:
            raise HTTPException(status_code=403, detail="缺少所需权限 scope")
    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """FastAPI 依赖：解析当前用户。

    - ``auth_enabled=False`` 时直接返回匿名用户，便于本地开发。
    - 否则校验 Bearer token，失败抛 401/403。
    """
    if not settings.auth_enabled:
        return {"sub": "anonymous", "name": "本地开发用户", "anonymous": True}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await verify_access_token(credentials.credentials, settings)
