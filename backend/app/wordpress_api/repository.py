from ..database import connection


def get_website_connection(website_id: int) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT id, url, wp_username AS "username",
              wp_application_password AS "encryptedPassword",
              wp_connected_at AS "connectedAt"
            FROM websites WHERE id = %s
            """,
            (website_id,),
        ).fetchone()
