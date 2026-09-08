from ..core.errors import ServiceError
from ..wordpress import (
    WordPressError,
    decrypt_password,
    encrypt_password,
    get_inventory,
    get_posts_seo,
    run_plugin_security_scan,
    update_plugin_status,
    verify_connection,
)
from . import repository
from .schemas import WordPressConnectionCreate, WordPressPluginUpdate


def _connected_website(website_id: int) -> dict:
    website = repository.get_website_connection(website_id)
    if not website:
        raise ServiceError("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        raise ServiceError("Website chưa kết nối WordPress.", 409)
    return website


def _password(website: dict) -> str:
    return decrypt_password(website["encryptedPassword"])


def inventory(website_id: int) -> dict:
    website = repository.get_website_connection(website_id)
    if not website:
        raise ServiceError("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return {"connected": False, "plugins": [], "themes": []}
    try:
        data = get_inventory(website["url"], website["username"], _password(website))
    except WordPressError as error:
        raise ServiceError(str(error), error.status_code) from error
    return {
        "connected": True,
        "username": website["username"],
        "connectedAt": website["connectedAt"],
        **data,
    }


def posts_seo(website_id: int) -> dict:
    website = _connected_website(website_id)
    try:
        return get_posts_seo(website["url"], website["username"], _password(website))
    except WordPressError as error:
        raise ServiceError(str(error), error.status_code) from error


def connect(website_id: int, payload: WordPressConnectionCreate) -> dict:
    username = (payload.username or "").strip()
    password = (payload.applicationPassword or "").replace(" ", "").strip()
    if not username or not password:
        raise ServiceError("Hãy nhập tên đăng nhập và Application Password.")
    website = repository.get_website_connection(website_id)
    if not website:
        raise ServiceError("Không tìm thấy website.", 404)
    try:
        profile = verify_connection(website["url"], username, password)
    except WordPressError as error:
        raise ServiceError(str(error), error.status_code) from error
    repository.save_connection(website_id, username, encrypt_password(password))
    return {"id": profile.get("id"), "name": profile.get("name")}


def disconnect(website_id: int) -> None:
    if not repository.clear_connection(website_id):
        raise ServiceError("Không tìm thấy website.", 404)


def change_plugin(website_id: int, payload: WordPressPluginUpdate) -> dict:
    plugin = (payload.plugin or "").strip()
    if not plugin:
        raise ServiceError("Plugin không hợp lệ.")
    website = _connected_website(website_id)
    try:
        result = update_plugin_status(
            website["url"], website["username"], _password(website), plugin, payload.status
        )
    except WordPressError as error:
        raise ServiceError(str(error), error.status_code) from error
    repository.add_plugin_status_audit(website_id, plugin, payload.status)
    return result


def security_scan(website_id: int) -> dict:
    website = _connected_website(website_id)
    try:
        result = run_plugin_security_scan(website["url"], website["username"], _password(website))
    except WordPressError as error:
        text = "Chưa cài hoặc chưa kích hoạt SiteOps Agent trên website WordPress." if error.status_code == 404 else str(error)
        raise ServiceError(text, error.status_code) from error
    saved = repository.save_security_scan(website_id, result)
    return {**result, **saved}


def latest_security_scan(website_id: int) -> dict | None:
    exists, scan = repository.latest_security_scan(website_id)
    if not exists:
        raise ServiceError("Không tìm thấy website.", 404)
    return scan
