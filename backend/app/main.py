from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .core.responses import message
from .customers.router import router as customers_router
from .database import close_pool, connection, ensure_scan_queue_schema, open_pool
from .malware.router import router as malware_router
from .monitoring.router import router as monitoring_router
from .notifications.router import router as notifications_router
from .reports.router import router as reports_router
from .websites.router import router as websites_router
from .websites.utils import normalize_website_address
from .wordpress_api.router import router as wordpress_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    ensure_scan_queue_schema()
    yield
    close_pool()


app = FastAPI(title="SiteOps API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep static paths before /websites/{website_id} to avoid ambiguous matching.
app.include_router(customers_router)
app.include_router(monitoring_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(websites_router)
app.include_router(wordpress_router)
app.include_router(malware_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["System"])
def health():
    try:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "connected"}
    except Exception:
        return message("Không thể kết nối cơ sở dữ liệu.", 503)


__all__ = ["app", "normalize_website_address"]
