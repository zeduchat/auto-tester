"""Snapshot a PR for review: metadata, checks, status, comments, files and diff.

Usage: python -I tools/collect_pr.py <fe|desktop|be|mobile> <pr>

Writes reviews/<folder>/<pr>/ (rename an older revision's folder to <pr>-<oldsha7> first)
and fetches refs/pull/<pr>/head into refs/review/<pr> in the repo's clone under pr-test/.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from repos import get  # noqa: E402


def run(*args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.exit(p.stderr)
    return p.stdout


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cfg, n = get(sys.argv[1]), int(sys.argv[2])
    repo, clone = cfg["repo"], cfg["clone"]
    out = cfg["reviews"] / str(n)
    out.mkdir(parents=True, exist_ok=True)
    api = lambda path: json.loads(run("gh", "api", f"repos/{repo}/{path}"))  # noqa: E731
    md = api(f"pulls/{n}")
    sha = md["head"]["sha"]
    data = {
        "metadata": md,
        "checks": api(f"commits/{sha}/check-runs?per_page=100"),
        "status": api(f"commits/{sha}/status?per_page=100"),
        "comments": api(f"issues/{n}/comments?per_page=100"),
        "files": [json.loads(line) for line in run(
            "gh", "api", "--paginate", f"repos/{repo}/pulls/{n}/files?per_page=100", "--jq", ".[] | @json").splitlines()],
    }
    for k, v in data.items():
        (out / f"{k}.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    git = ["git", "-c", "safe.directory=*"]
    run(*git, "fetch", "-q", "origin", f"+refs/pull/{n}/head:refs/review/{n}", md["base"]["ref"], cwd=clone)
    (out / "changes.diff").write_text(run(*git, "diff", f"{md['base']['sha']}...{sha}", cwd=clone), encoding="utf-8")
    print(md["title"], "|", md["user"]["login"], "| base", md["base"]["ref"], "| sha", sha[:7])
    print(f"+{md['additions']}/-{md['deletions']} files={md['changed_files']} commits={md['commits']}")
    print("--- BODY\n", md["body"])
    print("--- FILES")
    for f in data["files"]:
        print(f"{f['status']}\t+{f['additions']}/-{f['deletions']}\t{f['filename']}")
    print("--- COMMENTS")
    for c in data["comments"]:
        print(c["user"]["login"], ":", c["body"][:400].replace("\n", " "))


if __name__ == "__main__":
    main()
