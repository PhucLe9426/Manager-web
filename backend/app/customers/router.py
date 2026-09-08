from fastapi import APIRouter

from ..core.errors import ServiceError
from ..core.responses import message
from . import service
from .schemas import CustomerCreate, CustomerUpdate


router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("")
def list_customers():
    return {"customers": service.list_customers()}


@router.post("", status_code=201)
def create_customer(payload: CustomerCreate):
    try:
        return {"customer": service.create_customer(payload)}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.patch("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate):
    try:
        customer = service.update_customer(customer_id, payload)
        return {"customer": customer, "message": "Đã cập nhật khách hàng."}
    except ServiceError as error:
        return message(str(error), error.status_code)
