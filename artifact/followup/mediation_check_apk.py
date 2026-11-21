#!/usr/bin/env python3
"""Same DEX direct-call audit as `mediation_check.py` (same SINKS, OkHttp Call rule and approved transport classes), for
APKs given on the command line, written to a fresh directory (mediation_check.py has its APKs and output path fixed to the
recorded review-followup cohort, so it is not rerun). Not a complete-mediation proof: direct calls only; native code,
reflection, dynamic loading and IPC are not covered; unreachable library sites stay flagged.
Post-freeze static analysis (21/11, requested by C in PR #2): no device, no change to any run.
--callers 'Lpkg/Cls;->method' (repeatable): also list the direct callers of that method per APK (triage/find_callers.py).
Usage: mediation_check_apk.py --out results/round3/b2/mediation [--callers T ...] APK [APK ...]
"""
import argparse, collections, hashlib, json, re, sys, zipfile
from pathlib import Path

A = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(A / 'static'))
from dexscan import Dex, NET_EXACT  # noqa: E402
sys.path.insert(0, str(A / 'triage'))
from find_callers import callers  # noqa: E402

SINKS = NET_EXACT | {('Ljava/nio/channels/SocketChannel;', m) for m in ['write', 'connect']} | \
    {('Ljava/net/HttpURLConnection;', m) for m in ['connect', 'getOutputStream']} | \
    {('Ljavax/net/ssl/HttpsURLConnection;', m) for m in ['connect', 'getOutputStream']}          # = mediation_check.py
APPROVED = {'Lorg/residuelab/transport/HttpTransport;', 'Lorg/residuelab/transport/TlsTransport;'}


def approved(cls):
    return cls in APPROVED or cls.startswith('Lorg/residuelab/transport/HttpTransport$') or cls.startswith('Lorg/residuelab/transport/TlsTransport$')


def audit(apk):
    sites = []
    with zipfile.ZipFile(apk) as z:
        for name in sorted(z.namelist()):
            if not re.fullmatch(r'classes\d*\.dex', name): continue
            d = Dex(z.read(name))
            for cls, _, _, methods in d.classes():
                for method, off in methods:
                    for target in d.code_refs(off)[0]:
                        if target in SINKS or (target[0] in ['Lokhttp3/Call;', 'Lokhttp3/RealCall;'] and target[1] in ['execute', 'enqueue']):
                            sites.append({'caller': cls + '->' + method, 'target': '->'.join(target),
                                          'status': 'approved transport class' if approved(cls) else 'potential bypass; reachability/configuration review required'})
    pkg = lambda s: '/'.join(s['caller'].split(';')[0].lstrip('L').split('/')[:3])
    flagged = [s for s in sites if s['status'].startswith('potential')]
    return {'apk': str(Path(apk).resolve().relative_to(A)), 'sha256': hashlib.sha256(Path(apk).read_bytes()).hexdigest(),
            'sites': sites, 'approved_sites': len(sites) - len(flagged), 'potential_bypass_sites': len(flagged),
            'potential_bypass_by_package': dict(collections.Counter(pkg(s) for s in flagged).most_common()),
            'potential_bypass_by_target': dict(collections.Counter(s['target'] for s in flagged).most_common())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--callers', action='append', default=[]); ap.add_argument('apks', nargs='+'); a = ap.parse_args()
    out = A / a.out; assert not out.exists(), f'{out} exists (fresh directory only)'
    rows = [audit(p) for p in a.apks]
    for r, p in zip(rows, a.apks):
        r['callers'] = {t: callers(p, tuple(t.split('->'))) for t in a.callers}
    out.mkdir(parents=True)
    (out / 'mediation.json').write_text(json.dumps({'limitations': ['direct DEX calls only', 'no native, reflection, dynamic loading or IPC proof',
                                                                    'method overloads merged by inherited parser', 'library dead code remains flagged'],
                                                    'apks': rows}, indent=2) + '\n')
    for r in rows:
        print(r['apk'], r['sha256'][:8], 'sites', len(r['sites']), 'approved', r['approved_sites'], 'flagged', r['potential_bypass_sites'])
        print('  by package', r['potential_bypass_by_package']); print('  by target', r['potential_bypass_by_target'])
        for t, cs in r['callers'].items(): print('  callers of', t, cs)


if __name__ == '__main__':
    main()
