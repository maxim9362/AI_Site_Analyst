import re
from urllib.parse import urlparse, urlunparse


def normalize_public_url(value: str, default_scheme: str = "https") -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("sc-domain:"):
        return raw

    raw = raw.replace("\\", "/")
    raw = re.sub(r"^(https?://)(https?://)+", r"\2", raw, flags=re.IGNORECASE)
    if "://" not in raw:
        raw = f"{default_scheme}://{raw}"

    parsed = urlparse(raw)
    scheme = parsed.scheme or default_scheme
    netloc = parsed.netloc
    path = parsed.path

    if not netloc and path:
        path_parts = path.split("/", 1)
        netloc = path_parts[0]
        path = f"/{path_parts[1]}" if len(path_parts) > 1 else "/"

    if not path or set(path) == {"/"}:
        path = "/"

    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_gsc_property_url(value: str) -> str:
    return normalize_public_url(value)
