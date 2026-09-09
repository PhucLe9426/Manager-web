from io import BytesIO

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse

from ..core.errors import ServiceError
from ..core.responses import message
from . import service
from .schemas import ReportCreate


router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("")
def list_reports():
    return {"reports": service.list_reports()}


@router.post("", status_code=201)
def create_report(payload: ReportCreate):
    try:
        return {"report": service.create_report(payload), "message": "Đã tạo báo cáo."}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.get("/context/{website_id}")
def get_report_context(website_id: int):
    try:
        return service.report_context(website_id)
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.post("/{report_id}/items/{item_id}/attachments", status_code=201)
async def upload_report_attachment(report_id: int, item_id: int, file: UploadFile = File(...)):
    try:
        content = await file.read(8 * 1024 * 1024 + 1)
        attachment = service.save_attachment(report_id, item_id, file.filename or "minh-chung.jpg", content)
        return {"attachment": attachment, "message": "Đã tải ảnh minh chứng."}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.get("/{report_id}")
def get_report(report_id: int):
    try:
        return {"report": service.get_report(report_id)}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: int):
    try:
        content, filename = service.report_pdf(report_id)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(BytesIO(content), media_type="application/pdf", headers=headers)
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: int):
    try:
        service.delete_report(report_id)
        return None
    except ServiceError as error:
        return message(str(error), error.status_code)
