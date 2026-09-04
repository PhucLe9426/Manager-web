import base64
import hashlib
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener

from cryptography.fernet import Fernet, InvalidToken


class WordPressError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _cipher() -> Fernet:
    secret = os.getenv("WORDPRESS_CREDENTIALS_KEY", "siteops-dev-wordpress-key-change-me")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_password(password: str) -> str:
    return _cipher().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as error:
        raise WordPressError(
            "Không thể giải mã Application Password. Hãy kết nối lại WordPress.", 500
        ) from error


def _endpoint(site_url: str, path: str, namespace: str = "wp/v2") -> str:
    return f"{site_url.rstrip('/')}/wp-json/{namespace.strip('/')}/{path.lstrip('/')}"


def wordpress_request(
    site_url: str,
    username: str,
    application_password: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    namespace: str = "wp/v2",
    timeout_seconds: int = 20,
):
    if not site_url.lower().startswith("https://"):
        raise WordPressError(
            "WordPress phải sử dụng HTTPS để bảo vệ Application Password.", 400
        )

    authorization = base64.b64encode(
        f"{username}:{application_password}".encode("utf-8")
    ).decode("ascii")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        _endpoint(site_url, path, namespace),
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {authorization}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "SiteOps/1.0 WordPress Manager",
        },
    )

    try:
        with build_opener().open(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("message")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            detail = None
        if error.code in (401, 403):
            raise WordPressError(
                detail or "Sai tài khoản, Application Password hoặc tài khoản không đủ quyền.",
                error.code,
            ) from error
        if error.code == 404:
            raise WordPressError(
                "Website không hỗ trợ API quản lý WordPress này hoặc REST API đang bị chặn.",
                404,
            ) from error
        raise WordPressError(detail or f"WordPress trả về lỗi HTTP {error.code}.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WordPressError("Không thể kết nối tới REST API của WordPress.") from error


def verify_connection(site_url: str, username: str, password: str):
    return wordpress_request(site_url, username, password, "users/me?context=edit")


def get_inventory(site_url: str, username: str, password: str) -> dict:
    profile = verify_connection(site_url, username, password)
    plugins = wordpress_request(site_url, username, password, "plugins?context=edit")
    themes = wordpress_request(site_url, username, password, "themes?context=edit")
    return {
        "profile": {
            "id": profile.get("id"),
            "name": profile.get("name"),
            "roles": profile.get("roles", []),
        },
        "plugins": plugins or [],
        "themes": themes or [],
    }


def update_plugin_status(
    site_url: str, username: str, password: str, plugin: str, status: str
):
    plugin_path = quote(plugin, safe="")
    return wordpress_request(
        site_url,
        username,
        password,
        f"plugins/{plugin_path}",
        method="POST",
        payload={"status": status},
    )


def run_plugin_security_scan(site_url: str, username: str, password: str) -> dict:
    result = wordpress_request(
        site_url,
        username,
        password,
        "plugins?context=edit&siteops_security_scan_v14=1",
        timeout_seconds=180,
    )
    if isinstance(result, dict) and isinstance(result.get("siteopsPayload"), str):
        try:
            decoded = base64.b64decode(result["siteopsPayload"], validate=True)
            result = json.loads(decoded.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WordPressError("SiteOps Agent trả về gói dữ liệu không hợp lệ.") from error
    if not isinstance(result, dict) or not isinstance(result.get("plugins"), list):
        raise WordPressError("SiteOps Agent trả về dữ liệu không hợp lệ.")
    return result
