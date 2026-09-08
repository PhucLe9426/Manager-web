import re
from urllib.parse import urlsplit, urlunsplit


DOMAIN_PATTERN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)


def normalize_website_address(value: str | None) -> tuple[str, str] | None:
    raw_value = (value or "").strip()
    if not raw_value:
        return None
    candidate = raw_value if re.match(r"^https?://", raw_value, re.IGNORECASE) else f"https://{raw_value}"
    try:
        parsed = urlsplit(candidate)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme.lower() not in ("http", "https")
            or parsed.username
            or parsed.password
            or not DOMAIN_PATTERN.fullmatch(hostname)
        ):
            return None
        port = parsed.port
    except ValueError:
        return None
    netloc = hostname if port is None else f"{hostname}:{port}"
    return hostname, urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "", parsed.query, ""))
