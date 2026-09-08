from psycopg.errors import ForeignKeyViolation, UniqueViolation

from ..core.errors import ServiceError
from . import repository
from .schemas import WebsiteCreate
from .utils import normalize_website_address


def list_websites() -> list[dict]:
    return repository.list_all()


def create_website(payload: WebsiteCreate) -> dict:
    address = normalize_website_address(payload.domain)
    customer_id = payload.customerId
    if not address or not customer_id or customer_id <= 0:
        raise ServiceError("Khách hàng, tên miền hoặc URL không hợp lệ.")
    if not repository.customer_exists(customer_id):
        raise ServiceError("Không tìm thấy khách hàng đã chọn.", 404)
    domain, website_url = address
    try:
        return repository.create(customer_id, domain, website_url)
    except UniqueViolation as error:
        raise ServiceError("URL này đã tồn tại.", 409) from error
    except ForeignKeyViolation as error:
        raise ServiceError("Không tìm thấy khách hàng đã chọn.", 404) from error
    except Exception as error:
        raise ServiceError("Không thể thêm website.", 500) from error


def website_detail(website_id: int) -> dict:
    if website_id <= 0:
        raise ServiceError("Website không hợp lệ.")
    detail = repository.get_detail(website_id)
    if not detail:
        raise ServiceError("Không tìm thấy website.", 404)
    return detail
