from io import BytesIO
import os
from pathlib import Path
from xml.sax.saxutils import escape
from datetime import datetime, timedelta, timezone
from math import ceil

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("SiteOps", FONT_DIR / "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("SiteOps-Bold", FONT_DIR / "DejaVuSans-Bold.ttf"))


def _date(value) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:10]
    return value.strftime("%d/%m/%Y")


def _text(value, fallback="-") -> str:
    return str(value) if value not in (None, "") else fallback


def _safe(value, fallback="-") -> str:
    return escape(_text(value, fallback)).replace("\n", "<br/>")


def _datetime(value) -> str:
    if not value:
        return "Chưa có"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone(timedelta(hours=7))).strftime("%H:%M %d/%m/%Y")


def _post_date(value) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)[:10]


def _seconds(value) -> str:
    return f"{float(value):.2f}s" if value is not None else "Chưa có"


def _cls(value) -> str:
    return f"{float(value):.4f}" if value is not None else "Chưa có"


def _ssl_days(value) -> str:
    if not value:
        return "Chưa có"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return "Chưa có"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    days = max(0, ceil((value - datetime.now(timezone.utc)).total_seconds() / 86400))
    return f"{days} ngày"


def build_report_pdf(report: dict) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=report["title"],
        author="SiteOps Web Care Center",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("BodyVN", parent=styles["BodyText"], fontName="SiteOps", fontSize=9, leading=14, textColor=colors.HexColor("#33454f"))
    small = ParagraphStyle("SmallVN", parent=body, fontSize=7.5, leading=11, textColor=colors.HexColor("#687b84"))
    heading = ParagraphStyle("HeadingVN", parent=styles["Heading2"], fontName="SiteOps-Bold", fontSize=12, leading=16, textColor=colors.HexColor("#12394a"), spaceBefore=7, spaceAfter=7)
    title = ParagraphStyle("TitleVN", parent=styles["Title"], fontName="SiteOps-Bold", fontSize=20, leading=25, alignment=TA_CENTER, textColor=colors.HexColor("#12394a"))
    right = ParagraphStyle("RightVN", parent=small, alignment=TA_RIGHT)
    table_header = ParagraphStyle("TableHeaderVN", parent=small, fontName="SiteOps-Bold", textColor=colors.white)
    card_score = ParagraphStyle("CardScoreVN", parent=right, fontName="SiteOps-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#12394a"))

    story = [
        Table(
            [[Paragraph("<b>SITEOPS</b><br/><font size='7'>WEB CARE CENTER</font>", body), Paragraph(f"Ngày tạo: {_date(report['createdAt'])}", right)]],
            colWidths=[90 * mm, 88 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#79d4b6")), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]),
        ),
        Spacer(1, 10 * mm),
        Paragraph(_safe(report["title"]), title),
        Paragraph(f"Kỳ báo cáo: {_date(report['periodStart'])} - {_date(report['periodEnd'])}", ParagraphStyle("Period", parent=small, alignment=TA_CENTER)),
        Spacer(1, 8 * mm),
    ]

    info = [
        [Paragraph("KHÁCH HÀNG", small), Paragraph("WEBSITE", small)],
        [Paragraph(f"<b>{_safe(report['customerName'])}</b>", body), Paragraph(f"<b>{_safe(report['domain'])}</b><br/>{_safe(report['url'])}", body)],
        [Paragraph(f"Liên hệ: {_safe(report.get('contactName'))}<br/>{_safe(report.get('contactEmail'))}<br/>{_safe(report.get('contactPhone'))}", small), Paragraph("Báo cáo vận hành và bảo trì website", small)],
    ]
    story.append(Table(info, colWidths=[89 * mm, 89 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f5f1")), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d7e4e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7e4e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])))

    story.extend([Spacer(1, 6 * mm), Paragraph("Tổng quan & PageSpeed Insights", heading)])
    page_speed = report.get("pageSpeed") or report
    overview = [
        ["UPTIME 30 NGÀY", "THỜI GIAN PHẢN HỒI", "SSL CÒN HẠN"],
        [
            f"{float(page_speed.get('uptimePercent') or 0):.2f}%",
            f"{int(page_speed['responseTimeMs'])} ms" if page_speed.get("responseTimeMs") is not None else "Chưa có",
            _ssl_days(page_speed.get("sslExpiresAt")),
        ],
        [
            "Từ các lần kiểm tra HTTP",
            f"HTTP - {_datetime(page_speed.get('availabilityCheckedAt'))}",
            f"Hết hạn {_date(page_speed.get('sslExpiresAt'))}",
        ],
    ]
    story.append(Table(overview, colWidths=[59.33 * mm] * 3, style=TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "SiteOps"), ("FONTSIZE", (0, 0), (-1, 0), 6.5), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6d7e86")),
        ("FONTNAME", (0, 1), (-1, 1), "SiteOps-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 12), ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#12394a")),
        ("FONTNAME", (0, 2), (-1, 2), "SiteOps"), ("FONTSIZE", (0, 2), (-1, 2), 6.2), ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#7b8c93")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8f7")),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#d7e4e1")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#d7e4e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])))

    def page_speed_card(label: str, prefix: str) -> Table:
        score = page_speed.get(f"{prefix}Score")
        score_text = f"{score}/100" if score is not None else "Chưa có điểm"
        card = [
            [Paragraph(f"<b>{label}</b>", body), "", Paragraph(score_text, card_score)],
            [Paragraph("FCP", small), Paragraph("LCP", small), Paragraph("CLS", small)],
            [
                Paragraph(f"<b>{_seconds(page_speed.get(f'{prefix}FcpSeconds'))}</b>", body),
                Paragraph(f"<b>{_seconds(page_speed.get(f'{prefix}LcpSeconds'))}</b>", body),
                Paragraph(f"<b>{_cls(page_speed.get(f'{prefix}ClsScore'))}</b>", body),
            ],
            [Paragraph(f"Lần quét: {_datetime(page_speed.get(f'{prefix}CheckedAt'))}", small), "", ""],
        ]
        return Table(card, colWidths=[28.5 * mm] * 3, style=TableStyle([
            ("SPAN", (0, 0), (1, 0)), ("SPAN", (0, 3), (2, 3)),
            ("ALIGN", (0, 1), (-1, 2), "CENTER"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fbfa")),
            ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#d7e4e1")),
            ("LINEABOVE", (0, 1), (-1, 1), .35, colors.HexColor("#e1e9e7")),
            ("LINEABOVE", (0, 3), (-1, 3), .35, colors.HexColor("#e1e9e7")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))

    story.append(Spacer(1, 2.5 * mm))
    story.append(Table(
        [[page_speed_card("Mobile", "mobile"), page_speed_card("Desktop", "desktop")]],
        colWidths=[89 * mm, 89 * mm],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 2.5 * mm), ("LEFTPADDING", (1, 0), (1, 0), 2.5 * mm), ("RIGHTPADDING", (1, 0), (1, 0), 0)]),
    ))

    story.extend([Spacer(1, 5 * mm), Paragraph("Công việc đã thực hiện", heading)])
    work_rows = [[Paragraph("STT", table_header), Paragraph("Ngày", table_header), Paragraph("Nội dung công việc", table_header), Paragraph("Kết quả / ghi chú", table_header)]]
    for index, item in enumerate(report["items"], 1):
        work_rows.append([
            Paragraph(str(index), body), Paragraph(_date(item["performedDate"]), body),
            Paragraph(_safe(item["description"]), body), Paragraph(_safe(item.get("result"), "Đã hoàn thành"), body),
        ])
    story.append(Table(work_rows, colWidths=[11 * mm, 25 * mm, 72 * mm, 70 * mm], repeatRows=1, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12394a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "SiteOps-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfdcda")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce6e3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7faf9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])))

    evidence_items = [(index, item) for index, item in enumerate(report["items"], 1) if item.get("attachments")]
    if evidence_items:
        story.extend([Spacer(1, 5 * mm), Paragraph("Ảnh minh chứng công việc", heading)])
        upload_dir = Path(os.getenv("REPORT_UPLOAD_DIR", "/app/data/reports")).resolve()
        for item_index, item in evidence_items:
            story.append(Paragraph(f"<b>Công việc {item_index}:</b> {_safe(item['description'])}", body))
            for attachment in item["attachments"]:
                image_path = (upload_dir / attachment["storedName"]).resolve()
                if image_path.parent != upload_dir or not image_path.is_file():
                    story.append(Paragraph(f"Không tìm thấy ảnh: {_safe(attachment['originalName'])}", small))
                    continue
                report_image = ReportImage(str(image_path))
                report_image._restrictSize(170 * mm, 92 * mm)
                report_image.hAlign = "CENTER"
                caption = Paragraph(f"Ảnh minh chứng: {_safe(attachment['originalName'])}", ParagraphStyle("ImageCaptionVN", parent=small, alignment=TA_CENTER))
                story.extend([Spacer(1, 2 * mm), KeepTogether([report_image, Spacer(1, 1.5 * mm), caption]), Spacer(1, 3 * mm)])

    plugin_scan = report.get("pluginScan")
    story.extend([Spacer(1, 5 * mm), Paragraph("Plugin WordPress", heading)])
    if plugin_scan:
        plugin_summary = plugin_scan.get("summary") or {}
        plugins = plugin_scan.get("plugins") or []
        active_plugins = sum(bool(plugin.get("active")) for plugin in plugins)
        plugin_metrics = [
            ["TỔNG PLUGIN", "ĐANG BẬT", "CHECKSUM HỢP LỆ", "CẦN KIỂM TRA", "FILE THAY ĐỔI"],
            [
                _text(plugin_summary.get("total"), len(plugins)), active_plugins,
                _text(plugin_summary.get("verified"), 0), _text(plugin_summary.get("warning"), 0),
                _text(plugin_summary.get("modified"), 0),
            ],
        ]
        story.append(Table(plugin_metrics, colWidths=[35.6 * mm] * 5, style=TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "SiteOps"), ("FONTSIZE", (0, 0), (-1, 0), 6.4),
            ("FONTNAME", (0, 1), (-1, 1), "SiteOps-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 11),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6d7e86")), ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#12394a")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8f7")),
            ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#d7e4e1")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#d7e4e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])))
        story.append(Paragraph(f"Lần quét plugin: {_datetime(plugin_scan.get('checkedAt') or plugin_scan.get('scannedAt'))}", small))
    else:
        story.append(Paragraph("Chưa có dữ liệu quét plugin. Hãy chạy Quét bảo mật plugin trước khi tạo báo cáo.", body))

    seo_scan = report.get("seoScan")
    seo_block = [Spacer(1, 5 * mm), Paragraph("Bài viết & SEO", heading)]
    if seo_scan:
        seo_summary = seo_scan.get("summary") or {}
        posts = seo_scan.get("posts") or []
        seo_metrics = [
            ["TỔNG BÀI", "ĐÃ ĐĂNG", "ĐIỂM RANK MATH TB", "CẦN TỐI ƯU", "CHƯA CHẤM ĐIỂM"],
            [
                _text(seo_summary.get("total"), len(posts)), _text(seo_summary.get("published"), 0),
                _text(seo_summary.get("averageScore"), "Chưa có"), _text(seo_summary.get("needsAttention"), 0),
                max(0, int(seo_summary.get("total") or len(posts)) - int(seo_summary.get("rankMathScored") or 0)),
            ],
        ]
        seo_block.append(Table(seo_metrics, colWidths=[35.6 * mm] * 5, style=TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "SiteOps"), ("FONTSIZE", (0, 0), (-1, 0), 6.2),
            ("FONTNAME", (0, 1), (-1, 1), "SiteOps-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 11),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6d7e86")), ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#12394a")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8f7")),
            ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#d7e4e1")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#d7e4e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])))
        seo_block.append(Paragraph(f"Lần quét Bài viết & SEO: {_datetime(seo_scan.get('checkedAt'))}", small))
    else:
        seo_block.append(Paragraph("Chưa có dữ liệu Bài viết & SEO được lưu. Hãy bấm Làm mới SEO trên trang chi tiết website trước khi tạo báo cáo.", body))
    story.append(KeepTogether(seo_block))

    malware_scan = report.get("malwareScan")
    malware_block = [Spacer(1, 5 * mm), Paragraph("Malware Scanner", heading)]
    if malware_scan:
        malware_status = {"completed": "Đã hoàn tất", "failed": "Thất bại", "running": "Đang quét", "queued": "Đang chờ"}.get(malware_scan.get("status"), _text(malware_scan.get("status")))
        malware_metrics = [
            ["TRẠNG THÁI", "LOẠI QUÉT", "FILE ĐÃ QUÉT", "NGUY HIỂM", "CẢNH BÁO"],
            [
                malware_status, "Toàn bộ" if malware_scan.get("scanType") == "full" else "Nhanh",
                f"{malware_scan.get('scannedFiles') or 0}/{malware_scan.get('totalFiles') or 0}",
                malware_scan.get("dangerCount") or 0, malware_scan.get("warningCount") or 0,
            ],
        ]
        malware_block.append(Table(malware_metrics, colWidths=[35.6 * mm] * 5, style=TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "SiteOps"), ("FONTSIZE", (0, 0), (-1, 0), 6.4),
            ("FONTNAME", (0, 1), (-1, 1), "SiteOps-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6d7e86")), ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#12394a")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f8f7")),
            ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#d7e4e1")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#d7e4e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])))
        malware_block.append(Paragraph(f"Bắt đầu: {_datetime(malware_scan.get('startedAt'))} | Hoàn tất/cập nhật: {_datetime(malware_scan.get('completedAt') or malware_scan.get('updatedAt'))}", small))
    else:
        malware_block.append(Paragraph("Chưa có dữ liệu quét malware. Hãy chạy Quét nhanh hoặc Quét toàn bộ trước khi tạo báo cáo.", body))
    story.append(KeepTogether(malware_block))

    if report.get("summary"):
        story.extend([Spacer(1, 5 * mm), KeepTogether([Paragraph("Tổng kết", heading), Table([[Paragraph(_safe(report["summary"]), body)]], colWidths=[178 * mm], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f5f1")), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cce3dc")), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))])])

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("SiteOps", 7)
        canvas.setFillColor(colors.HexColor("#70818a"))
        canvas.drawString(16 * mm, 10 * mm, "SiteOps - Báo cáo chăm sóc website")
        canvas.drawRightString(194 * mm, 10 * mm, f"Trang {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()
