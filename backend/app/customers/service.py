from ..core.errors import ServiceError
from . import repository
from .schemas import CustomerCreate, CustomerUpdate


def _contact_data(payload: CustomerCreate) -> dict:
    return {
        "name": (payload.name or "").strip(),
        "contactName": (payload.contactName or "").strip() or None,
        "contactEmail": (payload.contactEmail or "").strip() or None,
        "contactPhone": (payload.contactPhone or "").strip() or None,
    }


def list_customers() -> list[dict]:
    return repository.list_all()


def create_customer(payload: CustomerCreate) -> dict:
    data = _contact_data(payload)
    if not data["name"]:
        raise ServiceError("Tên công ty không được để trống.")
    return repository.create(data)


def update_customer(customer_id: int, payload: CustomerUpdate) -> dict:
    if customer_id <= 0:
        raise ServiceError("Khách hàng không hợp lệ.")
    data = {**_contact_data(payload), "status": payload.status}
    if not data["name"] or data["status"] not in ("active", "paused"):
        raise ServiceError("Thông tin khách hàng không hợp lệ.")
    customer = repository.update(customer_id, data)
    if not customer:
        raise ServiceError("Không tìm thấy khách hàng.", 404)
    return customer
