from fastapi import APIRouter

from ..core.responses import message
from ..database import connection
from .schemas import CustomerCreate, CustomerUpdate


router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("")
def list_customers():
    with connection() as conn:
        customers = conn.execute(
            """
            SELECT c.id, c.name,
              c.contact_name AS "contactName",
              c.contact_email AS "contactEmail",
              c.contact_phone AS "contactPhone",
              c.status,
              COUNT(w.id)::int AS "websiteCount"
            FROM customers c
            LEFT JOIN websites w ON w.customer_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return {"customers": customers}


@router.post("", status_code=201)
def create_customer(payload: CustomerCreate):
    name = (payload.name or "").strip()
    if not name:
        return message("Tên công ty không được để trống.", 400)
    with connection() as conn:
        customer = conn.execute(
            """
            INSERT INTO customers (name, contact_name, contact_email, contact_phone)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name
            """,
            (
                name,
                (payload.contactName or "").strip() or None,
                (payload.contactEmail or "").strip() or None,
                (payload.contactPhone or "").strip() or None,
            ),
        ).fetchone()
    return {"customer": customer}


@router.patch("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate):
    if customer_id <= 0:
        return message("Khách hàng không hợp lệ.", 400)
    name = (payload.name or "").strip()
    if not name or payload.status not in ("active", "paused"):
        return message("Thông tin khách hàng không hợp lệ.", 400)
    with connection() as conn:
        customer = conn.execute(
            """
            UPDATE customers SET name = %s, contact_name = %s,
              contact_email = %s, contact_phone = %s, status = %s,
              updated_at = NOW()
            WHERE id = %s RETURNING id, name
            """,
            (
                name,
                (payload.contactName or "").strip() or None,
                (payload.contactEmail or "").strip() or None,
                (payload.contactPhone or "").strip() or None,
                payload.status,
                customer_id,
            ),
        ).fetchone()
    if not customer:
        return message("Không tìm thấy khách hàng.", 404)
    return {"customer": customer, "message": "Đã cập nhật khách hàng."}
