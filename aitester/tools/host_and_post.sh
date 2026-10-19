#!/usr/bin/env bash
# Usage: tools/host_and_post.sh <fe|desktop|be|mobile> <pr> <sha7> [followup]
# With "followup", posts zedutester-followup.md as an extra comment on an already reviewed
# head (AGENTS.md: corrections and new test results), refusing only an identical follow-up.
# Hosts reviews/<folder>/<pr>/shots/*.png on zeduchat/auto-tester's `screenshots` branch,
# replaces SCREENSHOT:<file>.png placeholders in zedutester-comment.md, re-checks that the
# PR is open, its head is still <sha7> and no ZeduTester review for <sha7> exists, then posts
# a NEW issue comment. Exits 1 without posting if any re-check fails.
set -euo pipefail
key=$1; n=$2; want=$3; mode=${4:-review}
ROOT=/d/Code/zedutester
case $key in
  fe) repo=zedu-fe; folder=open-prs ;;
  desktop) repo=zedu-desktop; folder=desktop-prs ;;
  be) repo=zedu-be; folder=be-prs ;;
  mobile) repo=zedu-mobile; folder=mobile-prs ;;
  *) echo "repo key must be fe, desktop, be or mobile"; exit 2 ;;
esac
D=$ROOT/reviews/$folder/$n
R=repos/zedu-hng/$repo
AT=$ROOT/pr-test/auto-tester   # clone of zeduchat/auto-tester, branch screenshots-local
base="https://raw.githubusercontent.com/zeduchat/auto-tester/screenshots/screenshots/$repo/$n"

full=$(gh api $R/pulls/$n --jq '.head.sha+" "+.state'); sha=${full%% *}; st=${full##* }; s7=${sha:0:7}
SRC="$D/zedutester-comment.md"
if [ "$mode" = followup ]; then
  SRC="$D/zedutester-followup.md"
  head300=$(head -c 300 "$SRC")
  dup=$(gh api "$R/issues/$n/comments?per_page=100" --paginate --jq '.[].body' | python -I -c "import sys; b=sys.stdin.read(); print(1 if sys.argv[1].strip() and sys.argv[1].strip() in b else 0)" "$head300")
else
dup=$(gh api "$R/issues/$n/comments?per_page=100" --paginate --jq ".[]|select((.body|test(\"ZeduTester review\")) and (.body|contains(\"$s7\")))|.id" | wc -l | tr -d ' ')
fi
echo "#$n head=$s7 state=$st dup=$dup"
if [ "$st" != open ] || [ "$s7" != "$want" ] || [ "$dup" != 0 ]; then echo "NOT POSTED #$n"; exit 1; fi

hosted() { case $1 in "$want"-*) echo "$1" ;; *) echo "$want-$1" ;; esac; }
if ls "$D"/shots/*.png >/dev/null 2>&1; then
  cd "$AT"
  git -c safe.directory=* switch -q screenshots-local
  git -c safe.directory=* pull -q --ff-only origin screenshots 2>/dev/null || true
  mkdir -p "screenshots/$repo/$n"
  for f in "$D"/shots/*.png; do cp "$f" "screenshots/$repo/$n/$(hosted "$(basename "$f")")"; done
  git -c safe.directory=* add -A
  git -c safe.directory=* commit -q -m "screenshots: $repo #$n" || true
  git -c safe.directory=* push -q origin screenshots-local:screenshots 2>&1 | grep -v "^remote:" || true
fi

python -I - "$SRC" "$D/comment-request.json" "$base" "$want" "$sha" <<'EOF'
import json, re, sys, urllib.request
src, out, base, want, sha = sys.argv[1:]
body = open(src, encoding="utf-8").read().rstrip("\n")
names = re.findall(r"SCREENSHOT:([\w.\-]+\.png)", body)
for name in names:
    hosted = name if name.startswith(want + "-") else f"{want}-{name}"
    url = f"{base}/{hosted}"
    if urllib.request.urlopen(urllib.request.Request(url, method="HEAD")).status != 200:
        sys.exit(f"screenshot not reachable: {url}")
    body = body.replace(f"SCREENSHOT:{name}", url)
if "SCREENSHOT:" in body:
    sys.exit("unreplaced SCREENSHOT placeholder left")
body = body.replace(f"/blob/{want}/", f"/blob/{sha}/")  # short-SHA blob links -> full SHA
json.dump({"body": body}, open(out, "w", encoding="ascii"), ensure_ascii=True)
print(f"{len(names)} screenshots linked")
EOF
gh api $R/issues/$n/comments --method POST --input "$D/comment-request.json" --jq '.html_url'
