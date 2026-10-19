"""Shared settings for the ZeduTester review loops. One loop per repo key."""
from pathlib import Path

ROOT = Path(r"D:\Code\zedutester")
PR_TEST = ROOT / "pr-test"
REVIEWS = ROOT / "reviews"
OWNER_LOGIN = "markessien"  # PRs by this account are skipped: we don't review our own work.

REPOS = {
    "fe": {"repo": "zedu-hng/zedu-fe", "clone": PR_TEST / "zedu-fe", "reviews": REVIEWS / "open-prs"},
    "desktop": {"repo": "zedu-hng/zedu-desktop", "clone": PR_TEST / "zedu-desktop", "reviews": REVIEWS / "desktop-prs"},
    "be": {"repo": "zedu-hng/zedu-be", "clone": PR_TEST / "zedu-be", "reviews": REVIEWS / "be-prs"},
    "mobile": {"repo": "zedu-hng/zedu-mobile", "clone": PR_TEST / "zedu-mobile", "reviews": REVIEWS / "mobile-prs"},
}


def get(key):
    if key not in REPOS:
        raise SystemExit(f"repo key must be one of {', '.join(REPOS)}")
    return REPOS[key]
