#!/usr/bin/env python3
"""Resolve the runtime dependency closure of androidx.work:work-runtime from Google Maven / Maven Central POMs
(highest version wins), download AAR/JAR artifacts and record SHA-256."""
import hashlib, os, re, sys, urllib.request, xml.etree.ElementTree as ET
GOOGLE = "https://dl.google.com/android/maven2"; CENTRAL = "https://repo1.maven.org/maven2"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deps")
NS = {"m": "http://maven.apache.org/POM/4.0.0"}
def url(base, g, a, v, ext): return f"{base}/{g.replace('.', '/')}/{a}/{v}/{a}-{v}.{ext}"
def fetch(g, a, v, ext):
    for base in (GOOGLE, CENTRAL):
        try:
            with urllib.request.urlopen(url(base, g, a, v, ext), timeout=60) as r:
                return r.read(), base
        except Exception:
            pass
    return None, None
def vkey(v): return [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", re.sub(r"[^0-9.\-]", "", v))]
best = {}
queue = [(sys.argv[1], sys.argv[2], sys.argv[3])]
SKIP = {"org.jetbrains:annotations", "androidx.annotation:annotation", "androidx.annotation:annotation-experimental",
        "com.google.errorprone:error_prone_annotations", "org.jspecify:jspecify"}
while queue:
    g, a, v = queue.pop()
    k = f"{g}:{a}"
    if k in SKIP: continue
    if k in best and vkey(best[k]) >= vkey(v): continue
    best[k] = v
    pom, _ = fetch(g, a, v, "pom")
    if not pom: print("NO POM", k, v); continue
    root = ET.fromstring(pom)
    for d in root.findall("./m:dependencies/m:dependency", NS):
        dg, da = d.findtext("m:groupId", "", NS), d.findtext("m:artifactId", "", NS)
        dv, sc = d.findtext("m:version", "", NS), d.findtext("m:scope", "compile", NS)
        opt = d.findtext("m:optional", "false", NS)
        if sc in ("test", "provided") or opt == "true" or not dv or "$" in dv: continue
        dv = dv.strip("[]").split(",")[0]
        queue.append((dg, da, dv))
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "SHA256SUMS"), "w") as sums:
    for k, v in sorted(best.items()):
        g, a = k.split(":")
        if k in SKIP: continue
        for ext in ("aar", "jar"):
            data, base = fetch(g, a, v, ext)
            if data:
                fn = f"{a}-{v}.{ext}"
                open(os.path.join(OUT, fn), "wb").write(data)
                sums.write(f"{hashlib.sha256(data).hexdigest()}  {fn}  {base}\n")
                print(k, v, ext)
                break
        else:
            print("NO ARTIFACT", k, v)
