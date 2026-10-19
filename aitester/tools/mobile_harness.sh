#!/usr/bin/env bash
# Local test harness only (never part of a review's subject): opens the message action sheets with
# setTimeout instead of InteractionManager.runAfterInteractions, whose callback never fires in the
# local debug build. Apply after mobile_switch.sh; mobile_switch.sh's checkout discards it.
C=/d/Code/zedutester/pr-test/zedu-mobile
for f in $(grep -rl "InteractionManager.runAfterInteractions(() => {" "$C/src/components/layout"); do
  python -I - "$f" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = re.sub(r"const task = InteractionManager\.runAfterInteractions\(\(\) => \{\n(.*?)\n    \}\);\n    return \(\) => task\.cancel\(\);",
           lambda m: "const t = setTimeout(() => {\n" + m.group(1) + "\n    }, 0);\n    return () => clearTimeout(t);", s, flags=re.S)
open(p, "w", encoding="utf-8").write(s)
PY
done
git -C "$C" diff --stat | tail -1
