"""Hard merge gates for a zedu-hng/zedu-desktop PR (AGENTS.md "Merge decision").

Checks GitHub data in code, never agent output. Usage:
  python -I merge_gates.py <pr> <reviewed_sha7> [--tickets-verified] [--finding-fixed] [--small-ui]

--tickets-verified  every ticket is a tested ✅ in this revision's review
--finding-fixed     at least one earlier ZeduTester finding was verified fixed
--small-ui          the reviewer judged the change a small UI change

Prints JSON: {"pass": bool, "gates": [{"gate", "pass", "detail"}]}.
"""
import json
import re
import subprocess
import sys

REPO = "zedu-hng/zedu-desktop"
MAX_LINES = 400
# Same exclusions as the repo's Size rule (pr-rules.yml size_exclude).
SIZE_EXCLUDE = re.compile(
    r"(^|/)(pubspec\.lock|Podfile\.lock)$|\.(g|freezed|mocks)\.dart$|(^|/)generated_plugin_registrant\."
)
FORBIDDEN = [
    (re.compile(r"^\.github/"), ".github/"),
    (re.compile(r"(^|/)(pubspec\.yaml|pubspec\.lock|Podfile|Podfile\.lock|package(-lock)?\.json|pnpm-lock\.yaml)$"), "dependency or lock file"),
    (re.compile(r"(^|/)\.env(\.|$)"), "env file"),
    (re.compile(r"auth|token|secret|payment|billing|credential|password", re.I), "auth, token, secret or payment code"),
]
DOCS_OR_TESTS = re.compile(r"(\.md$|^docs/|^test/|_test\.dart$)")
OK_CHECK = {"success", "skipped", "neutral"}


def gh(*args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        sys.exit(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return json.loads(out.stdout or "null")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pr, want = sys.argv[1], sys.argv[2]
    flags = set(sys.argv[3:])
    gates = []

    def gate(name, ok, detail=""):
        gates.append({"gate": name, "pass": bool(ok), "detail": detail})

    p = gh("api", f"repos/{REPO}/pulls/{pr}")
    sha = p["head"]["sha"]
    gate("Every ticket ✅ and verified by a test or reproduction", "--tickets-verified" in flags,
         "" if "--tickets-verified" in flags else "review has a ⚠️ or ❓ ticket, or a ✅ from reading only")
    gate("Head is the reviewed SHA, base is dev, not a draft",
         sha.startswith(want) and p["base"]["ref"] == "dev" and not p["draft"] and p["state"] == "open",
         f"head {sha[:7]}, base {p['base']['ref']}, draft {p['draft']}, state {p['state']}")

    statuses = gh("api", f"repos/{REPO}/commits/{sha}/status")["statuses"]
    runs = gh("api", f"repos/{REPO}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    bad = [f"{s['context']}: {s['state']}" for s in statuses if s["state"] != "success"]
    bad += [f"{r['name']}: {r['conclusion'] or r['status']}" for r in runs
            if r["status"] != "completed" or r["conclusion"] not in OK_CHECK]
    gate("Every status on the SHA is success, none pending", not bad, "; ".join(bad[:6]))

    q = ('query($n:Int!){repository(owner:"zedu-hng",name:"zedu-desktop"){pullRequest(number:$n){'
         'reviewThreads(first:100){nodes{isResolved}} labels(first:50){nodes{name}}}}}')
    d = gh("api", "graphql", "-f", f"query={q}", "-F", f"n={pr}")["data"]["repository"]["pullRequest"]
    open_threads = sum(1 for t in d["reviewThreads"]["nodes"] if not t["isResolved"])
    labels = [l["name"] for l in d["labels"]["nodes"]]
    gate("No unresolved review threads, no changes-requested label",
         open_threads == 0 and "changes-requested" not in labels,
         f"{open_threads} unresolved thread(s), labels {labels}")

    files = gh("api", "--paginate", f"repos/{REPO}/pulls/{pr}/files?per_page=100")
    names = [f["filename"] for f in files]
    hits = sorted({f"{n} ({why})" for n in names for rx, why in FORBIDDEN if rx.search(n)})
    gate("No .github/, dependency, lock, env, auth, token, secret or payment changes", not hits, "; ".join(hits[:8]))

    lines = sum(f["additions"] + f["deletions"] for f in files if not SIZE_EXCLUDE.search(f["filename"]))
    gate(f"At most {MAX_LINES} meaningful changed lines", lines <= MAX_LINES, f"{lines} lines")

    docs_tests = all(DOCS_OR_TESTS.search(n) for n in names)
    ok = "--finding-fixed" in flags or docs_tests or "--small-ui" in flags
    why = ("earlier finding verified fixed" if "--finding-fixed" in flags else
           "docs/tests only" if docs_tests else
           "small UI change" if "--small-ui" in flags else
           "first clean pass with code changes does not qualify")
    gate("An earlier finding was verified fixed, or docs/tests/small UI only", ok, why)

    print(json.dumps({"pass": all(g["pass"] for g in gates), "sha": sha[:7], "gates": gates},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
