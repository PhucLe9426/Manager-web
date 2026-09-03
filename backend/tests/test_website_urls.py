from app.main import normalize_website_address


def test_accepts_plain_domain():
    assert normalize_website_address("itsystems.vn") == (
        "itsystems.vn",
        "https://itsystems.vn",
    )


def test_accepts_full_url_with_path():
    assert normalize_website_address("https://itsystems.vn/store/") == (
        "itsystems.vn",
        "https://itsystems.vn/store/",
    )


def test_accepts_domain_with_path():
    assert normalize_website_address("itsystems.vn/contact/?from=siteops") == (
        "itsystems.vn",
        "https://itsystems.vn/contact/?from=siteops",
    )


def test_rejects_unsupported_protocol():
    assert normalize_website_address("ftp://itsystems.vn/store/") is None


def test_rejects_credentials_in_url():
    assert normalize_website_address("https://admin:secret@itsystems.vn/") is None
