"""
Generate demo pageview events with different traffic sources.

Usage:
    python demo_traffic_sources.py <SITE_ID> [--base-url http://localhost:8000]

Creates ~30 pageview events with realistic traffic source distribution:
  - Google organic: ~8 visits
  - Facebook social: ~5 visits
  - Direct: ~6 visits
  - Instagram: ~3 visits
  - WhatsApp: ~3 visits
  - Telegram: ~2 visits
  - Referral (other site): ~3 visits
"""

import argparse
import random
import string
import sys
import time
import urllib.request
import json


def rand_id(prefix="visitor"):
    chars = "0123456789abcdef"
    suffix = "".join(random.choice(chars) for _ in range(12))
    return f"{prefix}_{suffix}"


def send_event(base_url, site_id, event):
    data = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/events",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def build_event(site_id, visitor_id, session_id, referrer, url, path, title, metadata):
    return {
        "site_id": site_id,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "event_type": "pageview",
        "url": url,
        "path": path,
        "title": title,
        "referrer": referrer,
        "metadata": metadata,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate demo traffic source events")
    parser.add_argument("site_id", help="Site ID (e.g. site_abc123)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    site_id = args.site_id
    base = args.base_url.rstrip("/")
    site_url = f"{base}/demo?site_id={site_id}"

    # Traffic source scenarios with weights.
    scenarios = [
        # (referrer, url_suffix, metadata, weight, label)
        (
            "https://www.google.com/search?q=zemi+pro",
            "",
            {
                "traffic_source": "google",
                "traffic_channel": "organic_search",
                "referrer_host": "www.google.com",
            },
            8,
            "Google organic",
        ),
        (
            "https://www.facebook.com/share/zemi",
            "",
            {
                "traffic_source": "facebook",
                "traffic_channel": "social",
                "referrer_host": "www.facebook.com",
            },
            5,
            "Facebook",
        ),
        (
            "",
            "",
            {
                "traffic_source": "direct",
                "traffic_channel": "direct",
                "referrer_host": None,
            },
            6,
            "Direct",
        ),
        (
            "https://www.instagram.com/stories/zemi",
            "",
            {
                "traffic_source": "instagram",
                "traffic_channel": "social",
                "referrer_host": "www.instagram.com",
            },
            3,
            "Instagram",
        ),
        (
            "",
            "?utm_source=whatsapp&utm_medium=messenger&utm_campaign=group_share",
            {
                "traffic_source": "whatsapp",
                "traffic_channel": "messenger",
                "utm_source": "whatsapp",
                "utm_medium": "messenger",
                "utm_campaign": "group_share",
                "referrer_host": None,
            },
            3,
            "WhatsApp (UTM)",
        ),
        (
            "",
            "?utm_source=telegram&utm_medium=messenger&utm_campaign=channel_post",
            {
                "traffic_source": "telegram",
                "traffic_channel": "messenger",
                "utm_source": "telegram",
                "utm_medium": "messenger",
                "utm_campaign": "channel_post",
                "referrer_host": None,
            },
            2,
            "Telegram (UTM)",
        ),
        (
            "https://blog.example.com/top-services-2026",
            "",
            {
                "traffic_source": "blog.example.com",
                "traffic_channel": "referral",
                "referrer_host": "blog.example.com",
            },
            3,
            "Referral",
        ),
    ]

    # Also add some UTM campaign visits.
    utm_scenarios = [
        (
            "",
            "?utm_source=facebook&utm_medium=paid&utm_campaign=summer_promo",
            {
                "traffic_source": "facebook",
                "traffic_channel": "paid",
                "utm_source": "facebook",
                "utm_medium": "paid",
                "utm_campaign": "summer_promo",
                "referrer_host": None,
            },
            4,
            "Facebook paid (UTM)",
        ),
        (
            "",
            "?utm_source=google&utm_medium=cpc&utm_campaign=brand_keywords",
            {
                "traffic_source": "google",
                "traffic_channel": "cpc",
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign": "brand_keywords",
                "referrer_host": None,
            },
            3,
            "Google CPC (UTM)",
        ),
    ]

    all_scenarios = scenarios + utm_scenarios
    total = sum(s[3] for s in all_scenarios)

    print(f"Generating {total} demo pageview events for site: {site_id}")
    print(f"Base URL: {base}")
    print()

    pages = ["/", "/services", "/pricing", "/about", "/contacts", "/faq"]
    titles = ["ZemiPro", "Services", "Pricing", "About Us", "Contacts", "FAQ"]

    success = 0
    fail = 0

    for referrer, url_suffix, metadata, weight, label in all_scenarios:
        for i in range(weight):
            visitor_id = rand_id("visitor")
            session_id = rand_id("session")
            page_idx = random.randint(0, len(pages) - 1)
            path = pages[page_idx]
            title = titles[page_idx]
            url = f"{site_url}{url_suffix}"

            event = build_event(site_id, visitor_id, session_id, referrer, url, path, title, metadata)
            status = send_event(base, site_id, event)
            if status == 201:
                success += 1
                print(f"  [{label}] OK  {path}")
            else:
                fail += 1
                print(f"  [{label}] FAIL ({status}) {path}")

            time.sleep(0.05)

    print()
    print(f"Done: {success} created, {fail} failed")
    print(f"Open dashboard: {base}/admin/sites/{site_id}")


if __name__ == "__main__":
    main()
