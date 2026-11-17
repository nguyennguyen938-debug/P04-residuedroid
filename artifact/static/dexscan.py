#!/usr/bin/env python3
"""Stdlib-only static scanner for deferred-egress candidates in APKs.

For each APK: parse every classes*.dex (string/type/proto/method/class tables, class_data, code items), walk the
Dalvik bytecode to build an over-approximate call graph, and report
  * API presence: persisted deferred work (WorkManager, JobScheduler incl. setPersisted, AlarmManager,
    SyncAdapter, legacy GCM/Firebase dispatchers), network sinks, native code;
  * consent/opt-out signals: preference-key-like strings and UI strings (dex string pool + resources.arsc pool);
  * per deferred-job entry point (Worker/JobService/SyncAdapter subclasses): whether a network sink, a
    SharedPreferences read and a consent-like constant are reachable, and whether the job polls for stop.
This is a candidate screen, not violation evidence: reachability is over-approximate (name-based CHA,
new-instance => all methods of the allocated class) and cannot see runtime state.
"""
import json, re, struct, sys, zipfile, collections

# ------------------------------------------------------------------------------------------------ DEX parsing
def uleb(b, o):
    r = s = 0
    while True:
        x = b[o]; o += 1
        r |= (x & 0x7F) << s
        if x < 0x80:
            return r, o
        s += 7


def mutf8(b, o):
    n, o = uleb(b, o)
    e = b.index(0, o)
    return b[o:e].decode("utf-8", "replace")


WIDTH = [1] * 256
for op, w in {**{i: 1 for i in range(0x00, 0x02)}, 0x02: 2, 0x03: 3, 0x05: 2, 0x06: 3, 0x08: 2, 0x09: 3,
              0x13: 2, 0x14: 3, 0x15: 2, 0x16: 2, 0x17: 3, 0x18: 5, 0x19: 2, 0x1a: 2, 0x1b: 3, 0x1c: 2,
              0x1f: 2, 0x20: 2, 0x22: 2, 0x23: 2, 0x24: 3, 0x25: 3, 0x26: 3, 0x29: 2, 0x2a: 3, 0x2b: 3, 0x2c: 3,
              0xfa: 4, 0xfb: 4, 0xfc: 3, 0xfd: 3, 0xfe: 2, 0xff: 2}.items():
    WIDTH[op] = w
for op in range(0x2d, 0x38): WIDTH[op] = 2
for op in range(0x38, 0x3e): WIDTH[op] = 2
for op in range(0x44, 0x6e): WIDTH[op] = 2
for op in range(0x6e, 0x73): WIDTH[op] = 3
for op in range(0x74, 0x79): WIDTH[op] = 3
for op in range(0x90, 0xb0): WIDTH[op] = 2
for op in range(0xd0, 0xe3): WIDTH[op] = 2
INVOKE = set(range(0x6e, 0x73)) | set(range(0x74, 0x79))
NEWINST, CONSTSTR, CONSTSTRJ = 0x22, 0x1a, 0x1b


class Dex:
    def __init__(self, b):
        self.b = b
        (self.str_n, self.str_off, self.type_n, self.type_off, self.proto_n, self.proto_off,
         self.field_n, self.field_off, self.meth_n, self.meth_off, self.cls_n, self.cls_off) = struct.unpack_from("<12I", b, 0x38)
        self._s = {}
        self.types = [self.s(struct.unpack_from("<I", b, self.type_off + 4 * i)[0]) for i in range(self.type_n)]
        self.methods = []
        for i in range(self.meth_n):
            c, p, n = struct.unpack_from("<HHI", b, self.meth_off + 8 * i)
            self.methods.append((self.types[c], self.s(n)))

    def s(self, i):
        if i == 0xFFFFFFFF:
            return None
        if i not in self._s:
            off = struct.unpack_from("<I", self.b, self.str_off + 4 * i)[0]
            self._s[i] = mutf8(self.b, off)
        return self._s[i]

    def all_strings(self):
        return [self.s(i) for i in range(self.str_n)]

    def classes(self):
        b = self.b
        for i in range(self.cls_n):
            ci, af, sup, ioff, sf, ann, cdo, sv = struct.unpack_from("<IIIIIIII", b, self.cls_off + 32 * i)
            name = self.types[ci]
            sname = self.types[sup] if sup != 0xFFFFFFFF else None
            ifaces = []
            if ioff:
                n = struct.unpack_from("<I", b, ioff)[0]
                ifaces = [self.types[struct.unpack_from("<H", b, ioff + 4 + 2 * k)[0]] for k in range(n)]
            meths = []
            if cdo:
                o = cdo
                sfn, o = uleb(b, o); ifn, o = uleb(b, o); dmn, o = uleb(b, o); vmn, o = uleb(b, o)
                for _ in range(sfn + ifn):
                    _, o = uleb(b, o); _, o = uleb(b, o)
                for cnt in (dmn, vmn):
                    idx = 0
                    for _ in range(cnt):
                        d, o = uleb(b, o); idx += d
                        _, o = uleb(b, o)
                        code, o = uleb(b, o)
                        meths.append((self.methods[idx][1], code))
            yield name, sname, ifaces, meths

    def code_refs(self, code_off):
        """invoked method refs, allocated types, const strings of one code item"""
        b = self.b
        if not code_off:
            return [], [], []
        n = struct.unpack_from("<I", b, code_off + 12)[0]
        base = code_off + 16
        inv, new, strs = [], [], []
        pc = 0
        while pc < n:
            u = struct.unpack_from("<H", b, base + 2 * pc)[0]
            op = u & 0xFF
            if op == 0 and u != 0:
                ident = u
                if ident == 0x0100:
                    sz = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]; pc += 4 + sz * 2; continue
                if ident == 0x0200:
                    sz = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]; pc += 2 + sz * 4; continue
                if ident == 0x0300:
                    ew = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]
                    sz = struct.unpack_from("<I", b, base + 2 * pc + 4)[0]
                    pc += 4 + (sz * ew + 1) // 2; continue
            if op in INVOKE:
                mi = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]
                if mi < len(self.methods):
                    inv.append(self.methods[mi])
            elif op == NEWINST:
                ti = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]
                if ti < len(self.types):
                    new.append(self.types[ti])
            elif op == CONSTSTR:
                si = struct.unpack_from("<H", b, base + 2 * pc + 2)[0]
                strs.append(self.s(si))
            elif op == CONSTSTRJ:
                si = struct.unpack_from("<I", b, base + 2 * pc + 2)[0]
                strs.append(self.s(si))
            pc += WIDTH[op]
        return inv, new, strs


def arsc_strings(data):
    """global string pool of resources.arsc (UTF-8 or UTF-16)"""
    try:
        o = 12  # ResTable header
        typ, hsz, size = struct.unpack_from("<HHI", data, o)
        if typ != 0x0001:
            return []
        cnt, scnt, flags, sstart, ststart = struct.unpack_from("<IIIII", data, o + 8)
        utf8 = flags & 0x100
        offs = struct.unpack_from(f"<{cnt}I", data, o + hsz)
        out = []
        for so in offs[:200000]:
            p = o + sstart + so
            if utf8:
                l = data[p]; p += 2 if l & 0x80 else 1
                l2 = data[p]
                if l2 & 0x80:
                    l2 = ((l2 & 0x7F) << 8) | data[p + 1]; p += 2
                else:
                    p += 1
                out.append(data[p:p + l2].decode("utf-8", "replace"))
            else:
                l = struct.unpack_from("<H", data, p)[0]; p += 2
                if l & 0x8000:
                    l = ((l & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]; p += 2
                out.append(data[p:p + 2 * l].decode("utf-16-le", "replace"))
        return out
    except Exception:
        return []

# ------------------------------------------------------------------------------------------------ patterns
DEFERRED = {
    "workmanager": lambda c, m: c.startswith("Landroidx/work/WorkManager;") and m.startswith("enqueue"),
    "jobscheduler": lambda c, m: c == "Landroid/app/job/JobScheduler;" and m in ("schedule", "enqueue"),
    "job_persisted": lambda c, m: c == "Landroid/app/job/JobInfo$Builder;" and m == "setPersisted",
    "alarmmanager": lambda c, m: c == "Landroid/app/AlarmManager;" and m.startswith("set"),
    "syncadapter": lambda c, m: c == "Landroid/content/ContentResolver;" and m in ("requestSync", "addPeriodicSync"),
    "legacy_dispatch": lambda c, m: c.startswith("Lcom/firebase/jobdispatcher/") or c.startswith("Lcom/google/android/gms/gcm/GcmNetworkManager;"),
}
NET_PREFIX = ("Ljava/net/HttpURLConnection;", "Ljavax/net/ssl/HttpsURLConnection;", "Lokhttp3/", "Lcom/squareup/okhttp/",
              "Lretrofit2/", "Lcom/android/volley/", "Lio/ktor/client/", "Lorg/apache/http/client/",
              "Lcom/github/kittinunf/fuel/", "Lcom/loopj/android/http/", "Lcom/koushikdutta/ion/")
NET_EXACT = {("Ljava/net/URL;", "openConnection"), ("Ljava/net/URL;", "openStream"), ("Ljava/net/Socket;", "getOutputStream"),
             ("Ljava/net/Socket;", "connect"), ("Ljava/net/DatagramSocket;", "send")}
PREF_READ = {("Landroid/content/SharedPreferences;", m) for m in ("getBoolean", "getString", "getInt", "getLong", "getAll", "contains")}
STOP_POLL = {("Landroidx/work/ListenableWorker;", "isStopped"), ("Landroidx/work/Worker;", "isStopped"),
             ("Landroidx/work/CoroutineWorker;", "isStopped")}
SDKS = {"acra": "Lorg/acra/", "sentry": "Lio/sentry/", "matomo": ("Lorg/matomo/", "Lorg/piwik/"),
        "firebase_analytics": "Lcom/google/firebase/analytics/", "crashlytics": ("Lcom/google/firebase/crashlytics/", "Lcom/crashlytics/"),
        "mapbox_telemetry": "Lcom/mapbox/android/telemetry/", "bugsnag": "Lcom/bugsnag/", "countly": "Lly/count/",
        "mixpanel": "Lcom/mixpanel/", "amplitude": "Lcom/amplitude/", "segment": "Lcom/segment/analytics/",
        "appcenter": "Lcom/microsoft/appcenter/", "yandex_metrica": "Lcom/yandex/metrica/", "flurry": "Lcom/flurry/",
        "adjust": "Lcom/adjust/sdk/", "appsflyer": "Lcom/appsflyer/", "opentelemetry": "Lio/opentelemetry/",
        "gms_ads": "Lcom/google/android/gms/ads/", "facebook_sdk": "Lcom/facebook/appevents/"}
CALLBACKS = {"run", "call", "invoke", "invokeSuspend", "accept", "apply", "doWork", "onResponse", "onFailure",
             "handleMessage", "doInBackground", "emit", "onNext", "onSuccess", "execute", "subscribe"}
WORKER_BASES = {"Landroidx/work/Worker;", "Landroidx/work/CoroutineWorker;", "Landroidx/work/ListenableWorker;",
                "Landroidx/work/RxWorker;", "Landroidx/work/rxjava3/RxWorker;"}
ENTRY = {"worker": ({"doWork", "startWork", "createWork"}, WORKER_BASES),
         "jobservice": ({"onStartJob"}, {"Landroid/app/job/JobService;"}),
         "syncadapter": ({"onPerformSync"}, {"Landroid/content/AbstractThreadedSyncAdapter;"}),
         "gcmtask": ({"onRunTask"}, {"Lcom/google/android/gms/gcm/GcmTaskService;"})}
LIB_PREFIX = ("Landroidx/", "Landroid/support/", "Lcom/google/", "Lkotlin", "Lorg/acra/", "Lio/sentry/", "Lorg/matomo/",
              "Lcom/mapbox/", "Lcom/bugsnag/", "Lcom/microsoft/", "Lcom/facebook/", "Lio/opentelemetry/", "Lokhttp3/")
# consent key-like strings: identifier tokens (split on . _ -) containing a topic token and a control token
TOPIC_T = {"analytics", "analytic", "telemetry", "crash", "crashes", "crashreport", "crashreports", "crashreporting",
           "tracking", "consent", "diagnostics", "diagnostic", "metrics", "acra", "usagestats", "statistics"}
CONTROL_T = {"enable", "enabled", "disable", "disabled", "allow", "allowed", "opt", "optin", "optout", "consent",
             "send", "sending", "share", "sharing", "collect", "collection", "accept", "accepted", "agree", "on", "off"}
NOISE_PREFIX = ("m3_", "mtrl_", "exo_", "abc_", "design_", "material_", "uniffi_")


def is_consent_key(x):
    if not (4 <= len(x) <= 60) or x != x.lower() or " " in x or x.startswith(NOISE_PREFIX):
        return False
    toks = [t for t in re.split(r"[._\-]", x) if t]
    if len(toks) < 2:
        return False
    st = set(toks)
    if "usage" in st and st & {"stats", "statistics", "data"}:
        st.add("usagestats")
    return bool(st & TOPIC_T) and bool(st & CONTROL_T) and not (st & TOPIC_T == {"consent"} and st & CONTROL_T == {"consent"})


TOPIC_UI = r"(analytics|usage (statistics|data|stats)|anonymous (usage )?(data|statistics)|statistics|crash(es)? report(s|ing)?|telemetry|diagnostics?( data)?)"
UI_RES = [re.compile(r"(?i)\b(enable|disable|allow|send|sending|share|sharing|submit|collect|opt[ -]?(in|out)( of)?)\b.{0,40}\b" + TOPIC_UI + r"\b"),
          re.compile(r"(?i)\b" + TOPIC_UI + r"\b.{0,25}\b(enabled|disabled|consent|opt[ -]?(in|out))\b"),
          re.compile(r"(?i)^(anonymous )?(usage statistics|analytics|crash reports|crash reporting|telemetry)$"),
          re.compile(r"\b[Cc]onsent\b(?![a-z])")]


def is_consent_ui(x):
    return 6 <= len(x) <= 160 and any(r.search(x) for r in UI_RES)


def analyze_apk(path, max_nodes=8000):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    dexes = [Dex(z.read(n)) for n in sorted(names) if re.match(r"^classes\d*\.dex$", n)]
    native = any(n.startswith("lib/") and n.endswith(".so") for n in names)
    arsc = arsc_strings(z.read("resources.arsc")) if "resources.arsc" in names else []
    refs = set()
    strings = set()
    for d in dexes:
        refs.update(d.methods)
        strings.update(x for x in d.all_strings() if x)
    api = {k: any(f(c, m) for (c, m) in refs) for k, f in DEFERRED.items()}
    api["network"] = any(c.startswith(NET_PREFIX) or (c, m) in NET_EXACT for (c, m) in refs)
    api["native"] = native
    api["loadlibrary"] = ("Ljava/lang/System;", "loadLibrary") in refs
    types = set()
    for d in dexes:
        types.update(d.types)
    sdk = {k: any(t.startswith(p if isinstance(p, tuple) else (p,)) for t in types) for k, p in SDKS.items()}
    keys = sorted({s for s in strings if is_consent_key(s)})[:200]
    ui = sorted({s for s in arsc if is_consent_ui(s)})[:200]

    # ---- class hierarchy + per-method code refs
    sup, ifs, meths_of, code = {}, {}, collections.defaultdict(set), {}
    for di, d in enumerate(dexes):
        for name, sname, ifaces, meths in d.classes():
            if name in sup:
                continue
            sup[name] = sname; ifs[name] = ifaces
            for mn, co in meths:
                meths_of[name].add(mn)
                if co:
                    code.setdefault((name, mn), []).append((di, co))
    children = collections.defaultdict(set)
    for c, s in sup.items():
        if s: children[s].add(c)
        for i in ifs.get(c, []): children[i].add(c)

    def ancestors(c):
        seen = []
        stack = [c]
        while stack:
            x = stack.pop()
            for y in ([sup.get(x)] if sup.get(x) else []) + ifs.get(x, []):
                if y not in seen:
                    seen.append(y); stack.append(y)
        return seen

    def subs(c):
        out, stack = set(), [c]
        while stack:
            x = stack.pop()
            for y in children.get(x, ()):
                if y not in out:
                    out.add(y); stack.append(y)
        return out

    cache = {}
    subcache = {}

    def subs_c(c):
        if c not in subcache:
            subcache[c] = subs(c)
        return subcache[c]

    def refs_of(node):
        if node not in cache:
            inv, new, st = [], [], []
            for di, co in code.get(node, []):
                a, b, c = dexes[di].code_refs(co)
                inv += a; new += b; st += c
            cache[node] = (inv, new, st)
        return cache[node]

    entries = []
    for c in list(sup):
        anc = ancestors(c)
        for kind, (mnames, bases) in ENTRY.items():
            if c.startswith("Landroidx/work/"):
                continue  # WorkManager's own internal workers/services
            if any(a in bases for a in anc) and (meths_of[c] & mnames):
                entries.append((kind, c, sorted(meths_of[c] & mnames)))
    jobs = []
    for kind, c, ms in entries:
        start = [(c, m) for m in ms] + [(x, m) for x in sup if x.startswith(c[:-1] + "$") for m in meths_of[x]]
        seen = set(start)
        stack = collections.deque((x, 0) for x in start)   # BFS: depth = call hops from the entry
        net_depth = None
        r_net = r_pref = r_stop = False
        consts = set()
        net_api = set()
        while stack and len(seen) < max_nodes:
            node, dep = stack.popleft()
            inv, new, st = refs_of(node)
            consts.update(x for x in st if x)
            for (tc, tm) in inv:
                if tc.startswith(NET_PREFIX) or (tc, tm) in NET_EXACT:
                    r_net = True; net_api.add(tc.split("/")[-1].rstrip(";"))
                    net_depth = dep + 1 if net_depth is None else min(net_depth, dep + 1)
                    continue
                if (tc, tm) in PREF_READ:
                    r_pref = True
                if (tc, tm) in STOP_POLL or (tm == "isStopped" and tc in sup):
                    r_stop = True
                # CHA only below app-defined types; framework/library interfaces (Runnable.run, Function1.invoke)
                # are resolved through allocation edges instead, to avoid whole-program blow-up
                ext = tc.startswith(("Ljava/", "Ljavax/", "Landroid/", "Lkotlin/", "Lkotlinx/", "Landroidx/"))
                targets = [(tc, tm)] + ([] if ext else [(s2, tm) for s2 in subs_c(tc) if tm in meths_of[s2]][:50])
                for t in targets:
                    if t in code and t not in seen:
                        seen.add(t); stack.append((t, dep + 1))
            for nt in new:
                if nt.startswith(NET_PREFIX):
                    r_net = True; net_api.add(nt.split("/")[-1].rstrip(";"))
                    net_depth = dep + 1 if net_depth is None else min(net_depth, dep + 1)
                    continue
                for m in meths_of.get(nt, set()) & CALLBACKS:
                    t = (nt, m)
                    if t in code and t not in seen:
                        seen.add(t); stack.append((t, dep + 1))
        ckeys = sorted(x for x in consts if is_consent_key(x))[:20]
        jobs.append(dict(kind=kind, cls=c, library=c.startswith(LIB_PREFIX), reach_network=r_net, net_depth=net_depth, net_api=sorted(net_api)[:6],
                         reach_pref_read=r_pref, reach_consent_key=bool(ckeys), consent_keys=ckeys,
                         polls_stop=r_stop, nodes=len(seen), truncated=len(seen) >= max_nodes))
    return dict(api=api, sdk=sdk, consent_keys=keys, consent_ui=ui, jobs=jobs, n_dex=len(dexes))


if __name__ == "__main__":
    print(json.dumps(analyze_apk(sys.argv[1]), indent=1)[:6000])
