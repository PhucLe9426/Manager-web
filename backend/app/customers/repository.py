from ..database import connection


def list_all() -> list[dict]:
    with connection() as conn:
        return conn.execute(
            """
            SELECT c.id, c.name, c.contact_name AS "contactName",
              c.contact_email AS "contactEmail", c.contact_phone AS "contactPhone",
              c.status, COUNT(w.id)::int AS "websiteCount"
            FROM customers c LEFT JOIN websites w ON w.customer_id = c.id
            GROUP BY c.id ORDER BY c.created_at DESC
            """
        ).fetchall()


def create(data: dict) -> dict:
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO customers (name, contact_name, contact_email, contact_phone)
            VALUES (%s, %s, %s, %s) RETURNING id, name
            """,
            (data["name"], data["contactName"], data["contactEmail"], data["contactPhone"]),
        ).fetchone()


def update(customer_id: int, data: dict) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            UPDATE customers SET name = %s, contact_name = %s,
              contact_email = %s, contact_phone = %s, status = %s,
              updated_at = NOW() WHERE id = %s RETURNING id, name
            """,
            (
                data["name"], data["contactName"], data["contactEmail"],
                data["contactPhone"], data["status"], customer_id,
            ),
        ).fetchone()
