import html
import re
from pathlib import Path

DEMO_HTML_PATH = Path("app/static/demo/index.html")
DEMO_SITE_ID_MARKER = 'data-site-id="PUT_SITE_ID_HERE"'
SITE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")


def validate_demo_site_id(site_id: str) -> None:
    if not SITE_ID_PATTERN.fullmatch(site_id):
        raise ValueError("Invalid site_id")


def render_demo_html(site_id: str | None, demo_html_path: Path = DEMO_HTML_PATH) -> str:
    if site_id:
        validate_demo_site_id(site_id)

    html_text = demo_html_path.read_text(encoding="utf-8")
    escaped_site_id = html.escape(site_id or "", quote=True)
    return html_text.replace(DEMO_SITE_ID_MARKER, f'data-site-id="{escaped_site_id}"')
