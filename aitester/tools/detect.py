"""List PRs that need a ZeduTester review, and new human replies, for one repo.

Usage: python -I tools/detect.py <fe|desktop|be|mobile>

A PR needs a review when no "ZeduTester review" comment mentions its current head SHA
(NEW PR: never reviewed; NEW COMMIT: reviewed at an older head). PRs by OWNER_LOGIN are
listed as OWN PR and skipped. Replies are human comments newer than our latest ZeduTester
comment whose id is not in reviews/seen-replies.json (ids are stored as strings).
"""
import json
import subprocess
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from repos import OWNER_LOGIN, REVIEWS, get  # noqa: E402

BOTS = ("github-actions", "coderabbitai")


def api(path):
    out = subprocess.run(["gh", "api", "--paginate", path], capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout or "[]")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    repo = get(sys.argv[1])["repo"]
    seen = set(json.load(open(REVIEWS / "seen-replies.json", encoding="utf-8")))
    in_progress = (REVIEWS / "in-progress.txt").read_text(encoding="utf-8") if (REVIEWS / "in-progress.txt").exists() else ""
    for pr in api(f"repos/{repo}/pulls?state=open&per_page=100"):
        n, sha, author = pr["number"], pr["head"]["sha"][:7], pr["user"]["login"]
        comments = api(f"repos/{repo}/issues/{n}/comments?per_page=100")
        ours = [c for c in comments if "ZeduTester" in c["body"]]
        reviews = [c for c in ours if "ZeduTester review" in c["body"]]
        if author == OWNER_LOGIN:
            status = "OWN PR (skip)"
        elif f"{repo.split('/')[1]} {n}" in in_progress:
            status = "IN PROGRESS (skip)"
        elif any(sha in c["body"] for c in reviews):
            status = "ok"
        else:
            status = "NEW COMMIT" if reviews else "NEW PR"
        print(f"{repo} #{n} {sha} {author} {status} | {pr['title'][:70]}")
        if not ours:
            continue
        last = max(c["created_at"] for c in ours)
        for c in comments:
            user = c["user"]["login"]
            if str(c["id"]) in seen or user == OWNER_LOGIN or user.endswith("[bot]") or user in BOTS:
                continue
            if c["created_at"] > last:
                print(f"   REPLY {c['id']} {user} {c['created_at']} {c['body'][:300]!r}")


if __name__ == "__main__":
    main()
