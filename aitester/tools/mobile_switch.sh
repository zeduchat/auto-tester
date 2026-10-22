#!/usr/bin/env bash
# Point the running debug app at dev + PR <n> (or "dev"): builds branch zt/<n> in
# pr-test/zedu-mobile, then restarts the app so Metro serves the new JS.
# Usage: bash tools/mobile_switch.sh <n|dev>
set -e
C=/d/Code/zedutester/pr-test/zedu-mobile; A="$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"
git -C "$C" checkout -q -- src App.tsx 2>/dev/null || true   # drop any local harness
git -C "$C" fetch -q origin dev
if [ "$1" = dev ]; then git -C "$C" checkout -q --detach origin/dev
else
  git -C "$C" checkout -q -B "zt/$1" origin/dev
  if ! git -C "$C" -c user.name=zedutester -c user.email=zt@local merge -q --no-verify --no-edit "refs/review/$1"; then
    git -C "$C" merge --abort; echo "CONFLICT with dev: testing the PR head itself"
    git -C "$C" checkout -q --detach "refs/review/$1"
  fi
fi
echo "$(git -C "$C" rev-parse --abbrev-ref HEAD) $(git -C "$C" log -1 --format=%h)"
"$A" reverse tcp:8081 tcp:8081 >/dev/null
"$A" shell am force-stop net.emerj.zedu
"$A" shell monkey -p net.emerj.zedu -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
for i in $(seq 1 60); do python -I /d/Code/zedutester/tools/droid.py layout 2>/dev/null | grep -qE "^(Chats|Chat|Channels) \|" && break; sleep 2; done
python -I /d/Code/zedutester/tools/droid.py layout 2>/dev/null | grep -q "Open debugger" && "$A" shell input tap 996 2208 || true   # close the LogBox warning toast
true
echo ready
