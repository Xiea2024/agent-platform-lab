"""最小受保护 API 实验：验证 Keycloak 签发的 JWT + realm role (RBAC)。

教学要点：本服务只验证"你是谁 + 你有什么角色"（认证+授权），
不做任何租户数据隔离——JWT 认证 ≠ 租户隔离（见实验文档）。
"""
import os
import time

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

JWKS_URL = os.environ.get(
    "JWKS_URL",
    "http://keycloak.identity:8080/realms/lab/protocol/openid-connect/certs",
)
ISSUER = os.environ.get(
    "ISSUER", "http://keycloak.identity:8080/realms/lab"
)
REQUIRED_ROLE = "api-user"

app = FastAPI(title="lab-api")
bearer = HTTPBearer(auto_error=False)
_jwks_client: PyJWKClient | None = None


@app.on_event("startup")
def init_jwks():
    global _jwks_client
    # PyJWKClient 会缓存 JWKS 并按需刷新（模拟生产中常见的 JWKS 校验路径）
    _jwks_client = PyJWKClient(JWKS_URL)


def verify_token(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if creds is None:
        raise HTTPException(401, "missing bearer token")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(creds.credentials)
        claims = jwt.decode(
            creds.credentials,
            signing_key.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False},  # 生产应配置 audience mapper 并强校验
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e.__class__.__name__}")
    return claims


@app.get("/public")
def public():
    return {"message": "public endpoint, no auth required"}


@app.get("/protected")
def protected(claims: dict = Depends(verify_token)):
    roles = claims.get("realm_access", {}).get("roles", [])
    if REQUIRED_ROLE not in roles:
        # 认证通过（签名/issuer/exp 都合法）但角色不够 → 403
        raise HTTPException(403, f"missing required role: {REQUIRED_ROLE}")
    return {
        "message": "protected endpoint",
        "subject": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "client_id": claims.get("azp"),
        "roles": roles,
        "token_exp": claims.get("exp"),
        "server_time": int(time.time()),
    }
