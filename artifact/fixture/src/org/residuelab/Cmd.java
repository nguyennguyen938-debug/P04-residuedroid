package org.residuelab;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Harness command channel (adb am broadcast). */
public class Cmd extends BroadcastReceiver {
    @Override public void onReceive(Context c0, Intent i) {
        final Context c = c0.getApplicationContext();
        final String a = i.getAction() == null ? "" : i.getAction();
        final Db db = Db.get(c);
        String sp = i.getStringExtra("sink_port");
        if (sp != null) { db.putMeta("sink_port", sp); Fence.PORT = Integer.parseInt(sp); }
        String shost = i.getStringExtra("sink_host");
        if (shost != null) { db.putMeta("sink_host", shost); Fence.HOST = shost; }
        switch (a) {
            case "rl.SETUP": {
                for (String k : new String[]{"trial", "tenants", "substrate", "agg_delay", "up_delay", "sum_delay", "manual",
                        "resurrect_delay", "regrant_ms", "nrec", "race_delay", "sink_port", "sink_host"}) {
                    String v = i.getStringExtra(k); if (v != null) db.putMeta(k, v);
                }
                String inj = i.getStringExtra("inj");
                if (inj != null && !inj.isEmpty()) for (String kv : inj.split(",")) {
                    String[] p = kv.split(":"); db.putMeta("inj_" + p[0], p[1]);
                }
                Policy.initGrants(c);
                db.event(0, "SETUP", "trial=" + db.meta("trial", "") + ";variant=" + Model.variant(c).name);
                int n = Integer.parseInt(db.meta("nrec", "12"));
                long agg = Long.parseLong(db.meta("agg_delay", "3000")), up = Long.parseLong(db.meta("up_delay", "22000"));
                for (String s : db.meta("tenants", "").split(",")) {
                    if (s.isEmpty()) continue;
                    Model.Tenant t = Model.TENANTS[Integer.parseInt(s)];
                    Policy.collect(c, t, n);
                    if (t.hasSummary) Work.aggregate(c, t); // derivation happens before any withdrawal
                    if (t.dualPurpose) {
                        Sched.enqueue(c, t, Model.K_BACKUP, up, null, "setup");
                        Sched.enqueue(c, t, Model.K_PERSONAL, up, null, "setup");
                    } else Sched.enqueue(c, t, Model.K_UPLOAD, up, null, "setup");
                }
                setResultData("ok");
                break;
            }
            case "rl.WITHDRAW": {
                final String ts = i.getStringExtra("tenants");
                final PendingResult pr = goAsync();
                new Thread(() -> {
                    for (String s : ts.split(",")) if (!s.isEmpty()) doWithdraw(c, Model.TENANTS[Integer.parseInt(s)]);
                    pr.setResultData("ok"); pr.finish();
                }).start();
                break;
            }
            case "rl.REPORT": {
                final PendingResult pr = goAsync();
                new Thread(() -> { boolean ok = Sink.report(c); pr.setResultData(ok ? "ok" : "fail"); pr.finish(); }).start();
                break;
            }
            case "rl.BENCH": {
                final int n = i.getIntExtra("n", 1000);
                new Thread(() -> Bench.overhead(c, n)).start();
                setResultData("started");
                break;
            }
            case "rl.STRESS": {
                final int rounds = i.getIntExtra("rounds", 200);
                final long delay = i.getIntExtra("delay", 0);
                final int maxOff = i.getIntExtra("maxoff", 40);
                new Thread(() -> Bench.stress(c, rounds, delay, maxOff)).start();
                setResultData("started");
                break;
            }
            case "rl.CRASHWRITE": {
                new Thread(() -> Bench.crashWrite(c)).start();
                setResultData("started");
                break;
            }
            case "rl.CRASHCHECK": {
                setResultData(Bench.crashCheck(c));
                break;
            }
            default: setResultData("unknown");
        }
    }

    /** Explicit withdrawal; the reconsent tenant re-grants after regrant_ms and collects new-epoch records. */
    public static void doWithdraw(final Context c, final Model.Tenant t) {
        if (t.location) return; // OS-permission tenant: its "withdrawal" is pm revoke, issued by the harness
        Policy.withdraw(c, t);
        if (t.id == 5) new Thread(() -> {
            final Db db = Db.get(c);
            long rg = Long.parseLong(db.meta("regrant_ms", "1500"));
            Fence.sleep(rg);
            Policy.regrant(c, t);
            Policy.collect(c, t, 4);
            int id = Model.jobId(t.id, Model.K_UPLOAD);
            if (!Sched.pending(c, id)) Sched.enqueue(c, t, Model.K_UPLOAD, Long.parseLong(db.meta("resurrect_delay", "5000")), null, "regrant");
        }).start();
    }
}
