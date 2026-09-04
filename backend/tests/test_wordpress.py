import pytest

from app.wordpress import (
    WordPressError,
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
