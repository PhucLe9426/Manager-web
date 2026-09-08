from fastapi import APIRouter

from ..core.errors import ServiceError
from ..core.responses import message
from . import service
from .schemas import WebsiteCreate


router = APIRouter(prefix="/api/websites", tags=["Websites"])


@router.get("")
def list_websites():
    return {"websites": service.list_websites()}


@router.post("", status_code=201)
def create_website(payload: WebsiteCreate):
    try:
        return {"website": service.create_website(payload)}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.get("/{website_id}")
def website_detail(website_id: int):
    try:
        return service.website_detail(website_id)
    except ServiceError as error:
        return message(str(error), error.status_code)
