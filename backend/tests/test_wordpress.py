import pytest

from app.wordpress import (
    WordPressError,
    analyze_post_seo,
    decrypt_password,
    encrypt_password,
    wordpress_request,
)


def test_wordpress_password_is_encrypted(monkeypatch):
    monkeypatch.setenv("WORDPRESS_CREDENTIALS_KEY", "test-secret")
    encrypted = encrypt_password("abcd efgh ijkl")

    assert encrypted != "abcd efgh ijkl"
    assert decrypt_password(encrypted) == "abcd efgh ijkl"


def test_wordpress_credentials_require_https():
    with pytest.raises(WordPressError, match="HTTPS"):
        wordpress_request("http://example.com", "admin", "secret", "users/me")


def test_analyze_post_seo_reports_content_issues():
    post = {
        "id": 12,
        "title": {"raw": "Bài ngắn"},
        "content": {"raw": '<h1>Trùng H1</h1><img src="image.jpg">Nội dung ngắn.'},
        "excerpt": {"raw": ""},
        "slug": "bai-ngan",
        "status": "draft",
        "featured_media": 0,
        "categories": [],
        "tags": [],
        "siteops_rank_math": {"score": 42},
    }

    result = analyze_post_seo(post, "https://example.com")

    assert result["seoStatus"] == "critical"
    assert result["seoScore"] == 42
    assert result["imagesMissingAlt"] == 1
    assert result["h1Count"] == 1
    assert result["internalLinks"] == 0
    assert len(result["issues"]) >= 5


def test_analyze_post_seo_scores_well_structured_content():
    content = " ".join(["nội dung"] * 650)
    post = {
        "id": 13,
        "title": {"raw": "Hướng dẫn tối ưu website WordPress hiệu quả"},
        "content": {"raw": f'<p>{content}</p><img src="image.jpg" alt="Tối ưu WordPress"><a href="/dich-vu/">Dịch vụ</a>'},
        "excerpt": {"raw": "Tóm tắt bài viết tối ưu WordPress."},
        "slug": "huong-dan-toi-uu-wordpress",
        "status": "publish",
        "featured_media": 10,
        "categories": [1],
        "tags": [],
        "siteops_rank_math": {"score": 86},
    }

    result = analyze_post_seo(post, "https://example.com")

    assert result["seoScore"] == 86
    assert result["internalScore"] >= 85
    assert result["seoStatus"] == "good"
    assert result["imagesMissingAlt"] == 0
    assert result["internalLinks"] == 1
