#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
pdflatex -halt-on-error -interaction=nonstopmode main.tex > build-pass1.log
bibtex main > build-bibtex.log
pdflatex -halt-on-error -interaction=nonstopmode main.tex > build-pass2.log
pdflatex -halt-on-error -interaction=nonstopmode main.tex > build-pass3.log
pdfinfo main.pdf | awk '/Pages/{print "pages: " $2}'
python3 - <<'CHECK'
from pathlib import Path
s=Path('main.log').read_text(errors='replace')
print('overfull:',s.count('Overfull'))
for line in s.splitlines():
 if 'undefined' in line.lower() or line.startswith('!'):print(line)
if 'undefined references' in s or 'undefined citations' in s:raise SystemExit(1)
CHECK
