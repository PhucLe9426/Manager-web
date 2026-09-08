"""Low-level client for the authenticated WordPress REST API."""

import base64
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener

from cryptography.fernet import Fernet, InvalidToken


class WordPressError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class _PostContentAnalyzer(HTMLParser):
    def __init__(self, site_host: str):
        super().__init__(convert_charrefs=True)
        self.site_host = site_host
        self.text_parts: list[str] = []
        self.h1_count = 0
        self.image_count = 0
        self.images_missing_alt = 0
        self.internal_links = 0
        self.external_links = 0
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self._ignored_depth += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "img":
            self.image_count += 1
            if not (attributes.get("alt") or "").strip():
                self.images_missing_alt += 1
        elif tag == "a":
            href = (attributes.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                return
            target_host = (urlsplit(href).hostname or "").lower()
            if not target_host or target_host == self.site_host:
                self.internal_links += 1
            else:
                self.external_links += 1

    def handle_endtag(self, tag: str):
        if tag in ("script", "style") and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str):
        if not self._ignored_depth and data.strip():
            self.text_parts.append(data)


def _cipher() -> Fernet:
    secret = os.getenv("WORDPRESS_CREDENTIALS_KEY", "siteops-dev-wordpress-key-change-me")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_password(password: str) -> str:
    return _cipher().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as error:
        raise WordPressError(
            "Không thể giải mã Application Password. Hãy kết nối lại WordPress.", 500
        ) from error


def _endpoint(site_url: str, path: str, namespace: str = "wp/v2") -> str:
    return f"{site_url.rstrip('/')}/wp-json/{namespace.strip('/')}/{path.lstrip('/')}"


def wordpress_request(
    site_url: str,
    username: str,
    application_password: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    namespace: str = "wp/v2",
    timeout_seconds: int = 20,
    include_headers: bool = False,
):
    if not site_url.lower().startswith("https://"):
        raise WordPressError(
            "WordPress phải sử dụng HTTPS để bảo vệ Application Password.", 400
        )

    authorization = base64.b64encode(
        f"{username}:{application_password}".encode("utf-8")
    ).decode("ascii")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        _endpoint(site_url, path, namespace),
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {authorization}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "SiteOps/1.0 WordPress Manager",
        },
    )

    try:
        with build_opener().open(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            result = json.loads(body) if body else None
            if include_headers:
                return result, dict(response.headers.items())
            return result
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("message")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            detail = None
        if error.code in (401, 403):
            raise WordPressError(
                detail or "Sai tài khoản, Application Password hoặc tài khoản không đủ quyền.",
                error.code,
            ) from error
        if error.code == 404:
            raise WordPressError(
                "Website không hỗ trợ API quản lý WordPress này hoặc REST API đang bị chặn.",
                404,
            ) from error
        raise WordPressError(detail or f"WordPress trả về lỗi HTTP {error.code}.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WordPressError("Không thể kết nối tới REST API của WordPress.") from error


def verify_connection(site_url: str, username: str, password: str):
    return wordpress_request(site_url, username, password, "users/me?context=edit")


def get_inventory(site_url: str, username: str, password: str) -> dict:
    profile = verify_connection(site_url, username, password)
    plugins = wordpress_request(site_url, username, password, "plugins?context=edit")
    themes = wordpress_request(site_url, username, password, "themes?context=edit")
    return {
        "profile": {
            "id": profile.get("id"),
            "name": profile.get("name"),
            "roles": profile.get("roles", []),
        },
        "plugins": plugins or [],
        "themes": themes or [],
    }


def _rendered_text(value) -> str:
    if isinstance(value, dict):
        value = value.get("raw") or value.get("rendered") or ""
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def analyze_post_seo(post: dict, site_url: str) -> dict:
    title = _rendered_text(post.get("title"))
    excerpt = _rendered_text(post.get("excerpt"))
    content_value = post.get("content") or {}
    content = content_value.get("raw") or content_value.get("rendered") or "" if isinstance(content_value, dict) else str(content_value)
    analyzer = _PostContentAnalyzer((urlsplit(site_url).hostname or "").lower())
    analyzer.feed(content)
    plain_content = " ".join(analyzer.text_parts)
    word_count = len(re.findall(r"\b[^\W_]+(?:[-'][^\W_]+)*\b", plain_content, flags=re.UNICODE))
    title_length = len(title)
    slug = str(post.get("slug") or "")
    issues: list[str] = []
    score = 0

    if 30 <= title_length <= 60:
        score += 20
    else:
        score += 8 if title_length else 0
        issues.append("Tiêu đề nên dài khoảng 30–60 ký tự.")

    if word_count >= 600:
        score += 25
    elif word_count >= 300:
        score += 18
    else:
        score += 6 if word_count else 0
        issues.append("Nội dung dưới 300 từ.")

    if post.get("featured_media"):
        score += 10
    else:
        issues.append("Chưa có ảnh đại diện.")

    if analyzer.images_missing_alt == 0:
        score += 10
    else:
        issues.append(f"Có {analyzer.images_missing_alt} ảnh thiếu ALT.")

    if analyzer.h1_count == 0:
        score += 10
    else:
        issues.append("Nội dung có thẻ H1; dễ trùng với tiêu đề bài viết.")

    if analyzer.internal_links:
        score += 10
    else:
        issues.append("Chưa có liên kết nội bộ.")

    if excerpt:
        score += 10
    else:
        issues.append("Chưa có đoạn tóm tắt.")

    if slug and len(slug) <= 75:
        score += 5
    else:
        issues.append("Đường dẫn bài viết đang quá dài hoặc bị thiếu.")

    rank_math = post.get("siteops_rank_math") if isinstance(post.get("siteops_rank_math"), dict) else {}
    rank_math_score = rank_math.get("score")
    rank_math_score = int(rank_math_score) if isinstance(rank_math_score, (int, float)) else None
    rank_math_title = rank_math.get("title")
    rank_math_description = rank_math.get("description")
    rank_math_keyword = rank_math.get("focusKeyword")

    return {
        "id": post.get("id"),
        "title": title or "(Không có tiêu đề)",
        "slug": slug,
        "status": post.get("status") or "unknown",
        "link": post.get("link"),
        "editUrl": f"{site_url.rstrip('/')}/wp-admin/post.php?post={post.get('id')}&action=edit",
        "date": post.get("date"),
        "modified": post.get("modified"),
        "wordCount": word_count,
        "titleLength": title_length,
        "excerptLength": len(excerpt),
        "featuredImage": bool(post.get("featured_media")),
        "imageCount": analyzer.image_count,
        "imagesMissingAlt": analyzer.images_missing_alt,
        "h1Count": analyzer.h1_count,
        "internalLinks": analyzer.internal_links,
        "externalLinks": analyzer.external_links,
        "categoryCount": len(post.get("categories") or []),
        "tagCount": len(post.get("tags") or []),
        "seoScore": rank_math_score,
        "internalScore": score,
        "seoStatus": "unknown" if rank_math_score is None else "good" if rank_math_score >= 80 else "warning" if rank_math_score >= 60 else "critical",
        "issues": issues,
        "rankMath": {
            "available": rank_math_score is not None,
            "score": rank_math_score,
            "title": rank_math_title,
            "description": rank_math_description,
            "focusKeyword": rank_math_keyword,
        },
    }


def get_posts_seo(site_url: str, username: str, password: str) -> dict:
    params = {
        "context": "edit",
        "per_page": 100,
        "page": 1,
        "orderby": "date",
        "order": "desc",
        "status": "any",
        "_fields": "id,date,modified,slug,status,link,title,content,excerpt,featured_media,categories,tags,siteops_rank_math",
    }
    first_page, headers = wordpress_request(
        site_url,
        username,
        password,
        f"posts?{urlencode(params)}",
        include_headers=True,
    )
    posts = first_page or []
    total_pages = max(1, int(headers.get("X-WP-TotalPages", "1")))
    total_available = int(headers.get("X-WP-Total", str(len(posts))))

    def fetch_page(page: int) -> tuple[int, list]:
        page_params = {**params, "page": page}
        page_posts = wordpress_request(
            site_url, username, password, f"posts?{urlencode(page_params)}"
        ) or []
        return page, page_posts

    if total_pages > 1:
        pages: dict[int, list] = {}
        with ThreadPoolExecutor(max_workers=min(6, total_pages - 1)) as executor:
            futures = [executor.submit(fetch_page, page) for page in range(2, total_pages + 1)]
            for future in as_completed(futures):
                page, page_posts = future.result()
                pages[page] = page_posts
        for page in range(2, total_pages + 1):
            posts.extend(pages.get(page, []))

    analyzed = [analyze_post_seo(post, site_url) for post in posts]
    published = sum(post["status"] == "publish" for post in analyzed)
    scored_posts = [post for post in analyzed if post["seoScore"] is not None]
    needs_attention = sum(post["seoScore"] < 70 for post in scored_posts)

    return {
        "posts": analyzed,
        "summary": {
            "total": len(analyzed),
            "published": published,
            "draft": sum(post["status"] == "draft" for post in analyzed),
            "needsAttention": needs_attention,
            "averageScore": round(sum(post["seoScore"] for post in scored_posts) / len(scored_posts)) if scored_posts else None,
            "rankMathScored": len(scored_posts),
            "missingFeaturedImage": sum(not post["featuredImage"] for post in analyzed),
            "shortContent": sum(post["wordCount"] < 300 for post in analyzed),
            "rankMathDataAvailable": any(post["rankMath"]["available"] for post in analyzed),
            "totalAvailable": total_available,
            "allPostsLoaded": len(analyzed) >= total_available,
        },
    }


def update_plugin_status(
    site_url: str, username: str, password: str, plugin: str, status: str
):
    plugin_path = quote(plugin, safe="")
    return wordpress_request(
        site_url,
        username,
        password,
        f"plugins/{plugin_path}",
        method="POST",
        payload={"status": status},
    )


def run_plugin_security_scan(site_url: str, username: str, password: str) -> dict:
    result = wordpress_request(
        site_url,
        username,
        password,
        "plugins?context=edit&siteops_security_scan_v17=1",
        timeout_seconds=180,
    )
    if not (isinstance(result, dict) and isinstance(result.get("siteopsPayload"), str)):
        result = wordpress_request(
            site_url,
            username,
            password,
            "plugins?context=edit&siteops_security_scan_v16=1",
            timeout_seconds=180,
        )
    if not (isinstance(result, dict) and isinstance(result.get("siteopsPayload"), str)):
        result = wordpress_request(
            site_url,
            username,
            password,
            "plugins?context=edit&siteops_security_scan_v15=1",
            timeout_seconds=180,
        )
    if not (isinstance(result, dict) and isinstance(result.get("siteopsPayload"), str)):
        result = wordpress_request(
            site_url,
            username,
            password,
            "plugins?context=edit&siteops_security_scan_v14=1",
            timeout_seconds=180,
        )
    if isinstance(result, dict) and isinstance(result.get("siteopsPayload"), str):
        try:
            decoded = base64.b64decode(result["siteopsPayload"], validate=True)
            result = json.loads(decoded.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WordPressError("SiteOps Agent trả về gói dữ liệu không hợp lệ.") from error
    if not isinstance(result, dict) or not isinstance(result.get("plugins"), list):
        raise WordPressError("SiteOps Agent trả về dữ liệu không hợp lệ.")
    return result
