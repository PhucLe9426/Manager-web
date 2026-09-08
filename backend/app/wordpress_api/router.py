import json

from fastapi import APIRouter

from ..core.responses import message
from ..database import connection
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
from .repository import get_website_connection
from .schemas import WordPressConnectionCreate, WordPressPluginUpdate


router = APIRouter(prefix="/api/websites/{website_id}/wordpress", tags=["WordPress"])


def connected_website_or_response(website_id: int):
    website = get_website_connection(website_id)
    if not website:
        return None, message("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return None, message("Website chưa kết nối WordPress.", 409)
    return website, None


@router.get("")
def wordpress_inventory(website_id: int):
    website = get_website_connection(website_id)
    if not website:
        return message("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return {"connected": False, "plugins": [], "themes": []}
    try:
        inventory = get_inventory(
            website["url"], website["username"], decrypt_password(website["encryptedPassword"])
        )
        return {
            "connected": True,
            "username": website["username"],
            "connectedAt": website["connectedAt"],
            **inventory,
        }
    except WordPressError as error:
        return message(str(error), error.status_code)


@router.get("/posts-seo")
def wordpress_posts_seo(website_id: int):
    website, response = connected_website_or_response(website_id)
    if response:
        return response
    try:
        return get_posts_seo(
            website["url"], website["username"], decrypt_password(website["encryptedPassword"])
        )
    except WordPressError as error:
        return message(str(error), error.status_code)


@router.post("/connection")
def connect_wordpress(website_id: int, payload: WordPressConnectionCreate):
    username = (payload.username or "").strip()
    password = (payload.applicationPassword or "").replace(" ", "").strip()
    if not username or not password:
        return message("Hãy nhập tên đăng nhập và Application Password.", 400)
    website = get_website_connection(website_id)
    if not website:
        return message("Không tìm thấy website.", 404)
    try:
        profile = verify_connection(website["url"], username, password)
    except WordPressError as error:
        return message(str(error), error.status_code)
    with connection() as conn:
        conn.execute(
            """
            UPDATE websites SET wp_username = %s, wp_application_password = %s,
              wp_connected_at = NOW(), updated_at = NOW() WHERE id = %s
            """,
            (username, encrypt_password(password), website_id),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.connected', 'website', %s, %s::jsonb)
            """,
            (str(website_id), json.dumps({"source": "application-password"})),
        )
    return {
        "message": "Đã kết nối WordPress thành công.",
        "profile": {"id": profile.get("id"), "name": profile.get("name")},
    }


@router.delete("/connection")
def disconnect_wordpress(website_id: int):
    with connection() as conn:
        website = conn.execute(
            """
            UPDATE websites SET wp_username = NULL, wp_application_password = NULL,
              wp_connected_at = NULL, updated_at = NOW()
            WHERE id = %s RETURNING id
            """,
            (website_id,),
        ).fetchone()
        if not website:
            return message("Không tìm thấy website.", 404)
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id)
            VALUES ('wordpress.disconnected', 'website', %s)
            """,
            (str(website_id),),
        )
    return {"message": "Đã ngắt kết nối WordPress."}


@router.patch("/plugin")
def change_wordpress_plugin(website_id: int, payload: WordPressPluginUpdate):
    plugin = (payload.plugin or "").strip()
    if not plugin:
        return message("Plugin không hợp lệ.", 400)
    website, response = connected_website_or_response(website_id)
    if response:
        return response
    try:
        result = update_plugin_status(
            website["url"], website["username"],
            decrypt_password(website["encryptedPassword"]), plugin, payload.status,
        )
    except WordPressError as error:
        return message(str(error), error.status_code)
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.plugin_status_changed', 'website', %s, %s::jsonb)
            """,
            (str(website_id), json.dumps({"plugin": plugin, "status": payload.status})),
        )
    return {"message": "Đã cập nhật trạng thái plugin.", "plugin": result}


@router.post("/security-scan")
def scan_wordpress_plugins(website_id: int):
    website, response = connected_website_or_response(website_id)
    if response:
        return response
    try:
        result = run_plugin_security_scan(
            website["url"], website["username"], decrypt_password(website["encryptedPassword"])
        )
    except WordPressError as error:
        if error.status_code == 404:
            return message("Chưa cài hoặc chưa kích hoạt SiteOps Agent trên website WordPress.", 404)
        return message(str(error), error.status_code)
    with connection() as conn:
        saved = conn.execute(
            """
            INSERT INTO wordpress_security_scans (website_id, summary, results, checked_at)
            VALUES (%s, %s::jsonb, %s::jsonb, NOW())
            RETURNING id, checked_at AS "checkedAt"
            """,
            (website_id, json.dumps(result.get("summary", {})), json.dumps(result)),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.security_scan', 'website', %s, %s::jsonb)
            """,
            (str(website_id), json.dumps(result.get("summary", {}))),
        )
    return {"scan": {**result, **saved}}


@router.get("/security-scan/latest")
def latest_wordpress_security_scan(website_id: int):
    with connection() as conn:
        if not conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone():
            return message("Không tìm thấy website.", 404)
        scan = conn.execute(
            """
            SELECT id, results, checked_at AS "checkedAt"
            FROM wordpress_security_scans WHERE website_id = %s
            ORDER BY checked_at DESC LIMIT 1
            """,
            (website_id,),
        ).fetchone()
    return {"scan": scan}
