#!/usr/bin/env python3
"""C8 pre-submission check, run from manuscript/ after build.sh. Exit code 1 if anything blocks submission.

Checks: body length (the bibliography may start on page 13 at the latest, so the body is at most 12 pages), overfull
boxes, undefined references, generated macros still rendering ?? that the paper uses, en or em dashes in prose,
and the LLM-use note."""
import glob, re, sys
from pathlib import Path

log = Path("main.log").read_text(errors="replace")
src = {f: Path(f).read_text(encoding="utf-8") for f in glob.glob("sections/*.tex") + ["main.tex"]}
problems = []

# The conclusion ends with \label{body-end}; its page in main.aux is the last page of the body.
m = re.search(r"\\newlabel\{body-end\}\{\{[^}]*\}\{(\d+)\}", Path("main.aux").read_text(errors="replace"))
body_end = int(m.group(1)) if m else 0
if not m:
    problems.append("label body-end missing from main.aux")
elif body_end > 12:
    problems.append(f"body ends on page {body_end}, past the 12-page limit")
if log.count("Overfull"):
    problems.append(f"{log.count('Overfull')} overfull box(es)")
if re.search(r"undefined (references|citations)|Reference .* undefined", log):
    problems.append("undefined references or citations")

used = set()
for text in src.values():
    used |= set(re.findall(r"\\([A-Za-z]+)", "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("%"))))
for gen in ("generated/macros.tex", "generated/tests_macros.tex"):
    for name, value in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\\xspace\}", Path(gen).read_text(encoding="utf-8")):
        if "??" in value and name in used:
            problems.append(f"macro \\{name} renders ?? ({gen})")

for f, text in src.items():
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("%"):
            continue
        if "\u2013" in line or "\u2014" in line or re.search(r"(?<!-)--(?!-)|---", line):
            problems.append(f"dash in {f}:{i}")

if not re.search(r"(?i)large language model|LLM", src["main.tex"]):
    problems.append("LLM-use note missing from main.tex")

print(f"body ends on page {body_end}; " + ("OK" if not problems else f"{len(problems)} problem(s)"))
for p in problems:
    print(" -", p)
sys.exit(1 if problems else 0)
