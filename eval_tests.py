import os
import re
import sys
import json
import time
from urllib.request import urlopen, Request


BASE_URL = os.getenv("BEACON_BASE_URL", "http://155.138.164.238")


def fetch(path: str):
    url = f"{BASE_URL}{path}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def title_quality(title: str) -> bool:
    if not title or len(title) < 12:
        return False
    if re.search(r"\b(VS|Vs|vs)\b\s+\d+$", title):
        return False
    if re.match(r"^[^A-Za-z]*$", title):
        return False
    if len(re.findall(r"\b\w+\b", title)) < 2:
        return False
    return True


def run():
    health = fetch("/api/health")
    print("Health:", health.get("status"))

    topics = fetch("/api/topics").get("topics", [])
    print("Topics:", len(topics))

    bad = []
    for t in topics:
        title = t.get("canonical_title") or t.get("title") or ""
        if not title_quality(title):
            bad.append(title)

    print("Bad titles:", len(bad))
    for b in bad[:10]:
        print(" -", b)

    ok_ratio = 1.0 - (len(bad) / max(1, len(topics)))
    print(f"Title quality ratio: {ok_ratio:.2%}")
    if ok_ratio < 0.7:
        sys.exit(1)


if __name__ == "__main__":
    run()


