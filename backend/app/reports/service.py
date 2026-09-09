import re
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from ..core.errors import ServiceError
from . import repository
from .pdf import build_report_pdf
from .schemas import ReportCreate


def list_reports() -> list[dict]:
    return repository.list_all()


def create_report(payload: ReportCreate) -> dict:
    if payload.websiteId <= 0 or not repository.website_exists(payload.websiteId):
        raise ServiceError("Không tìm thấy website đã chọn.", 404)
    if payload.periodEnd < payload.periodStart:
        raise ServiceError("Ngày kết thúc không được nhỏ hơn ngày bắt đầu.")
    title = payload.title.strip()
    items = [
        {
            "performedDate": item.performedDate,
            "description": item.description.strip(),
            "result": (item.result or "").strip() or None,
        }
        for item in payload.items
        if item.description.strip()
    ]
    if not title or not items:
        raise ServiceError("Báo cáo cần có tiêu đề và ít nhất một công việc.")
    return repository.create(
        {
            "websiteId": payload.websiteId,
            "title": title,
            "periodStart": payload.periodStart,
            "periodEnd": payload.periodEnd,
            "summary": (payload.summary or "").strip() or None,
            "items": items,
        }
    )


def get_report(report_id: int) -> dict:
    report = repository.get_by_id(report_id)
    if not report:
        raise ServiceError("Không tìm thấy báo cáo.", 404)
    return report


def report_context(website_id: int) -> dict:
    if website_id <= 0:
        raise ServiceError("Website không hợp lệ.")
    context = repository.get_context(website_id)
    if context is None:
        raise ServiceError("Không tìm thấy website.", 404)
    return context


def save_attachment(report_id: int, item_id: int, original_name: str, content: bytes) -> dict:
    if report_id <= 0 or item_id <= 0 or not repository.item_belongs_to_report(report_id, item_id):
        raise ServiceError("Không tìm thấy công việc trong báo cáo.", 404)
    if repository.attachment_count(item_id) >= 5:
        raise ServiceError("Mỗi công việc chỉ được đính kèm tối đa 5 ảnh.")
    if not content or len(content) > 8 * 1024 * 1024:
        raise ServiceError("Ảnh minh chứng phải nhỏ hơn hoặc bằng 8 MB.")
    try:
        source = Image.open(BytesIO(content))
        source.load()
        if source.format not in {"JPEG", "PNG", "WEBP"}:
            raise ServiceError("Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP.")
        image = ImageOps.exif_transpose(source)
        image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ServiceError("File đính kèm không phải ảnh hợp lệ.") from error

    upload_dir = Path(os.getenv("REPORT_UPLOAD_DIR", "/app/data/reports")).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.jpg"
    target = (upload_dir / stored_name).resolve()
    if target.parent != upload_dir:
        raise ServiceError("Đường dẫn lưu ảnh không hợp lệ.", 500)
    encoded = output.getvalue()
    target.write_bytes(encoded)
    safe_original_name = Path(original_name or "minh-chung.jpg").name[:255]
    try:
        return repository.create_attachment(item_id, safe_original_name, stored_name, len(encoded))
    except Exception:
        target.unlink(missing_ok=True)
        raise


def report_pdf(report_id: int) -> tuple[bytes, str]:
    report = get_report(report_id)
    domain = re.sub(r"[^a-zA-Z0-9.-]+", "-", report["domain"]).strip("-.") or "website"
    return build_report_pdf(report), f"bao-cao-{domain}-{report_id}.pdf"


def delete_report(report_id: int) -> None:
    stored_names = repository.attachment_names_for_report(report_id)
    if not repository.delete(report_id):
        raise ServiceError("Không tìm thấy báo cáo.", 404)
    upload_dir = Path(os.getenv("REPORT_UPLOAD_DIR", "/app/data/reports")).resolve()
    for stored_name in stored_names:
        target = (upload_dir / stored_name).resolve()
        if target.parent == upload_dir:
            target.unlink(missing_ok=True)
