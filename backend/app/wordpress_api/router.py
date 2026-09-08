from fastapi import APIRouter

from ..core.errors import ServiceError
from ..core.responses import message
from . import service
from .schemas import WordPressConnectionCreate, WordPressPluginUpdate


router = APIRouter(prefix="/api/websites/{website_id}/wordpress", tags=["WordPress"])


def service_response(callback):
    try:
        return callback()
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.get("")
def wordpress_inventory(website_id: int):
    return service_response(lambda: service.inventory(website_id))


@router.get("/posts-seo")
def wordpress_posts_seo(website_id: int):
    return service_response(lambda: service.posts_seo(website_id))


@router.post("/connection")
def connect_wordpress(website_id: int, payload: WordPressConnectionCreate):
    def connect():
        profile = service.connect(website_id, payload)
        return {"message": "Đã kết nối WordPress thành công.", "profile": profile}
    return service_response(connect)


@router.delete("/connection")
def disconnect_wordpress(website_id: int):
    def disconnect():
        service.disconnect(website_id)
        return {"message": "Đã ngắt kết nối WordPress."}
    return service_response(disconnect)


@router.patch("/plugin")
def change_wordpress_plugin(website_id: int, payload: WordPressPluginUpdate):
    def change():
        plugin = service.change_plugin(website_id, payload)
        return {"message": "Đã cập nhật trạng thái plugin.", "plugin": plugin}
    return service_response(change)


@router.post("/security-scan")
def scan_wordpress_plugins(website_id: int):
    return service_response(lambda: {"scan": service.security_scan(website_id)})


@router.get("/security-scan/latest")
def latest_wordpress_security_scan(website_id: int):
    return service_response(lambda: {"scan": service.latest_security_scan(website_id)})
