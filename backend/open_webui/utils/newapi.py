from __future__ import annotations

import base64
import logging
import os
from typing import Any

import aiohttp
from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.config import Config
from open_webui.models.users import UserModel
from open_webui.utils.json_codec import JSONCodec

log = logging.getLogger(__name__)

DEFAULT_NEW_API_BASE_URL = 'http://localhost:3000'
AUTO_TOKEN_NAME = 'OpenWebUI-Auto'


def _strip_v1_suffix(url: str) -> str:
    cleaned = url.strip().rstrip('/')
    for suffix in ('/api/v1', '/v1'):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip('/')
            break
    return cleaned


async def get_newapi_base_url() -> str:
    """
    Resolve New API base URL:
    1. Environment variable NEW_API_BASE_URL if set
    2. First URL in Open WebUI's OPENAI_API_BASE_URLS (with /v1 stripped), if not api.openai.com
    3. Fallback to http://localhost:3000
    """
    env_url = os.getenv('NEW_API_BASE_URL', '').strip()
    if env_url:
        base_url = _strip_v1_suffix(env_url)
        await _ensure_openai_base_url(base_url)
        return base_url

    api_base_urls = await Config.get('openai.api_base_urls') or []
    for raw_url in api_base_urls:
        if raw_url and 'api.openai.com' not in raw_url:
            return _strip_v1_suffix(raw_url)

    base_url = _strip_v1_suffix(DEFAULT_NEW_API_BASE_URL)
    await _ensure_openai_base_url(base_url)
    return base_url


async def _ensure_openai_base_url(newapi_base_url: str) -> None:
    """
    If Open WebUI's openai.api_base_urls is still only pointing to the default
    api.openai.com, point it to {newapi_base_url}/v1 so models and chat work out-of-the-box.
    """
    try:
        api_base_urls = await Config.get('openai.api_base_urls') or []
        target_v1_url = f'{newapi_base_url.rstrip("/")}/v1'
        if not api_base_urls or api_base_urls == ['https://api.openai.com/v1']:
            await Config.upsert(
                {
                    'openai.enable': True,
                    'openai.api_base_urls': [target_v1_url],
                    'openai.api_keys': [''],
                }
            )
    except Exception as e:
        log.debug('Failed to auto-update openai.api_base_urls: %s', e)


def _encrypt_password_rsa_oaep(password: str, public_key_pem: str) -> str | None:
    """Encrypt password with RSA-OAEP (SHA-256) when New API enables password encryption."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        pub_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
        ciphertext = pub_key.encrypt(
            password.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode('ascii')
    except Exception as e:
        log.warning('Failed to encrypt password for New API login: %s', e)
        return None


def _extract_tokens_list(token_json: dict[str, Any]) -> list[dict[str, Any]]:
    data = token_json.get('data')
    if isinstance(data, dict):
        items = data.get('items') or data.get('data') or []
        return items if isinstance(items, list) else []
    if isinstance(data, list):
        return data
    return []


def _select_best_token(tokens: list[dict[str, Any]]) -> dict[str, Any] | None:
    enabled_tokens = [t for t in tokens if isinstance(t, dict) and t.get('status') == 1]
    if not enabled_tokens:
        return None

    # 1. Prefer token created by Open WebUI
    for t in enabled_tokens:
        if t.get('name') == AUTO_TOKEN_NAME:
            return t

    # 2. Prefer unlimited quota token without model limits
    for t in enabled_tokens:
        if t.get('unlimited_quota') and not t.get('model_limits_enabled'):
            return t

    # 3. Prefer any unlimited quota token
    for t in enabled_tokens:
        if t.get('unlimited_quota'):
            return t

    return enabled_tokens[0]


async def _fetch_unmasked_key(
    session: aiohttp.ClientSession,
    base_url: str,
    token_obj: dict[str, Any],
    headers: dict[str, str],
) -> str | None:
    token_id = token_obj.get('id')
    raw_key = str(token_obj.get('key') or '').strip()

    # In newer New API versions, GET /api/token/ masks the key with '*' and
    # provides POST /api/token/{id}/key to retrieve the full key.
    if token_id is not None and (not raw_key or '*' in raw_key):
        try:
            async with session.post(
                f'{base_url}/api/token/{token_id}/key',
                headers=headers,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as key_resp:
                if key_resp.status == 200:
                    key_json = await key_resp.json(loads=JSONCodec.loads)
                    if isinstance(key_json, dict) and key_json.get('success'):
                        key_data = key_json.get('data')
                        if isinstance(key_data, dict) and key_data.get('key'):
                            raw_key = str(key_data['key']).strip()
                        elif isinstance(key_data, str) and key_data.strip():
                            raw_key = key_data.strip()
        except Exception as e:
            log.warning('Failed to fetch full key for token %s from New API: %s', token_id, e)

    if not raw_key or '*' in raw_key:
        return None

    return raw_key if raw_key.startswith('sk-') else f'sk-{raw_key}'


async def authenticate_with_newapi(identifier: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Authenticate user against New API and retrieve (or create) their personal API key.

    Returns:
        (user_payload, error_message)
        where user_payload contains:
        {
            'id': int | str,
            'username': str,
            'display_name': str,
            'email': str,
            'role': 'admin' | 'user',
            'api_key': 'sk-...',
        }
    """
    base_url = await get_newapi_base_url()
    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            login_payload: dict[str, Any] = {
                'username': identifier.strip(),
                'password': password,
            }

            # Check if New API has password login encryption enabled
            try:
                async with session.get(
                    f'{base_url}/api/user/login/encryption-key',
                    ssl=AIOHTTP_CLIENT_SESSION_SSL,
                ) as enc_resp:
                    if enc_resp.status == 200:
                        enc_json = await enc_resp.json(loads=JSONCodec.loads)
                        enc_data = (enc_json or {}).get('data') or {}
                        if enc_data.get('enabled') and enc_data.get('public_key') and enc_data.get('kid'):
                            encrypted = _encrypt_password_rsa_oaep(password, enc_data['public_key'])
                            if encrypted:
                                login_payload['password_encrypted'] = encrypted
                                login_payload['encryption_key_id'] = enc_data['kid']
            except Exception as e:
                log.debug('New API encryption-key check skipped: %s', e)

            # 1. Authenticate user via POST /api/user/login
            async with session.post(
                f'{base_url}/api/user/login',
                json=login_payload,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as login_resp:
                try:
                    login_json = await login_resp.json(loads=JSONCodec.loads)
                except Exception:
                    return None, f'New API 登录响应异常 (HTTP {login_resp.status})'

                if login_resp.status != 200 or not isinstance(login_json, dict) or not login_json.get('success'):
                    msg = (login_json.get('message') if isinstance(login_json, dict) else None) or '用户名或密码错误'
                    return None, msg

                raw_data = login_json.get('data') or {}
                if isinstance(raw_data, dict) and isinstance(raw_data.get('user'), dict):
                    user_data = raw_data['user']
                    access_token = raw_data.get('access_token')
                elif isinstance(raw_data, dict):
                    user_data = raw_data
                    access_token = None
                else:
                    return None, 'New API 返回的用户数据格式无效'

            user_id = user_data.get('id')
            username = str(user_data.get('username') or identifier.strip())
            display_name = str(user_data.get('display_name') or username)
            raw_email = str(user_data.get('email') or '').strip().lower()
            email = raw_email if ('@' in raw_email) else f'{username.lower()}@newapi.local'

            # New API role: 1 = common user, 10 = admin, 100 = root
            raw_role = user_data.get('role', 1)
            try:
                role = 'admin' if int(raw_role) >= 10 else 'user'
            except (ValueError, TypeError):
                role = 'user'

            auth_headers: dict[str, str] = {
                'Content-Type': 'application/json',
            }
            if user_id is not None:
                auth_headers['New-Api-User'] = str(user_id)
            if access_token:
                auth_headers['Authorization'] = f'Bearer {access_token}'

            # 2. Query user's existing API tokens
            tokens: list[dict[str, Any]] = []
            async with session.get(
                f'{base_url}/api/token/?p=1&size=20',
                headers=auth_headers,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as token_resp:
                if token_resp.status == 200:
                    token_json = await token_resp.json(loads=JSONCodec.loads)
                    if isinstance(token_json, dict) and token_json.get('success'):
                        tokens = _extract_tokens_list(token_json)

            selected_token = _select_best_token(tokens)

            # 3. Auto-create an unlimited token if the user has no active token
            if not selected_token:
                create_payload = {
                    'name': AUTO_TOKEN_NAME,
                    'remain_quota': 500000,
                    'expired_time': -1,
                    'unlimited_quota': True,
                    'model_limits_enabled': False,
                    'model_limits': '',
                    'allow_ips': '',
                    'group': '',
                }
                async with session.post(
                    f'{base_url}/api/token/',
                    json=create_payload,
                    headers=auth_headers,
                    ssl=AIOHTTP_CLIENT_SESSION_SSL,
                ) as create_resp:
                    if create_resp.status == 200:
                        async with session.get(
                            f'{base_url}/api/token/?p=1&size=20',
                            headers=auth_headers,
                            ssl=AIOHTTP_CLIENT_SESSION_SSL,
                        ) as refetch_resp:
                            if refetch_resp.status == 200:
                                refetch_json = await refetch_resp.json(loads=JSONCodec.loads)
                                if isinstance(refetch_json, dict) and refetch_json.get('success'):
                                    tokens = _extract_tokens_list(refetch_json)
                                    selected_token = _select_best_token(tokens)

            if not selected_token:
                return None, '无法在 New API 中获取或创建该用户的 API 令牌，请检查用户令牌配额'

            # 4. Retrieve full unmasked API key (sk-...)
            api_key = await _fetch_unmasked_key(session, base_url, selected_token, auth_headers)
            if not api_key:
                return None, '无法从 New API 获取明文 API Key'

            return {
                'id': user_id,
                'username': username,
                'display_name': display_name,
                'email': email,
                'role': role,
                'api_key': api_key,
            }, None

    except aiohttp.ClientError as e:
        log.error('New API connection error (%s): %s', base_url, e)
        return None, f'无法连接到 New API 服务 ({base_url})'
    except Exception as e:
        log.exception('Unexpected error during New API authentication: %s', e)
        return None, f'New API 认证异常: {e}'


def get_user_newapi_key(user: UserModel | None, default_key: str | None = None) -> str | None:
    """Return the logged-in user's New API key if stored on user.info, otherwise default_key."""
    if user is not None:
        info = getattr(user, 'info', None)
        if isinstance(info, dict):
            user_key = info.get('newapi_key')
            if isinstance(user_key, str) and user_key.strip():
                return user_key.strip()
    return default_key
