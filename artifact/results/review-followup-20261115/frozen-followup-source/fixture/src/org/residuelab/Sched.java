package org.residuelab;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.os.PersistableBundle;
import android.os.SystemClock;

/** Deferred-work substrate: persisted JobScheduler jobs (default) or AlarmManager alarms re-armed from the outbox. */
public final class Sched {
    public static String declaredScope(Model.Tenant t, int kind) {
        return kind == Model.K_SUMMARY ? t.summaryDeclared : t.scope;
    }
    public static String purposeOf(Model.Tenant t, int kind) {
        switch (kind) {
            case Model.K_UPLOAD: return t.purpose;
            case Model.K_AGG: return "aggregate";
            case Model.K_SUMMARY: return t.summaryDeclared.equals("diagnostics") ? "diagnostics" : "analytics";
            case Model.K_BACKUP: return "backup";
            case Model.K_PERSONAL: return "personalization";
        }
        return "?";
    }
    static String substrate(Context c) { return Db.get(c).meta("substrate", "job"); }
    static boolean manual(Context c) { return Db.get(c).meta("manual", "0").equals("1"); }

    /** Enqueue persisted deferred work; returns false if the enqueue-time check refused it. */
    public static boolean enqueue(Context c, Model.Tenant t, int kind, long delayMs, PersistableBundle extras, String why) {
        Model.Variant v = Model.variant(c);
        Db db = Db.get(c);
        if (v.enqueueCheck && (v.matched ? ChunkFence.earlyBlocked(c,t,kind,extras) : Policy.blockedConv(c, t, declaredScope(t, kind), purposeOf(t, kind)))) {
            db.event(t.id, "ENQ_SKIP", "kind=" + kind + ";why=" + why);
            return false;
        }
        if (manual(c) && (why.equals("setup") || why.equals("aggregator"))) delayMs = 600_000; // harness force-runs these
        int id = Model.jobId(t.id, kind);
        if (extras == null) extras = new PersistableBundle();
        extras.putInt("tenant", t.id); extras.putInt("kind", kind);
        if (substrate(c).equals("work")) {
            bridge(c, "enqueue", id, delayMs, extras);
        } else if (substrate(c).equals("alarm")) {
            AlarmManager am = c.getSystemService(AlarmManager.class);
            am.setExactAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + delayMs,
                    alarmPi(c, id, extras, PendingIntent.FLAG_UPDATE_CURRENT));
        } else {
            JobInfo ji = new JobInfo.Builder(id, new ComponentName(c, UpJob.class))
                    .setPersisted(true).setMinimumLatency(delayMs).setOverrideDeadline(delayMs + 15_000)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setExtras(extras).build();
            c.getSystemService(JobScheduler.class).schedule(ji);
        }
        db.event(t.id, "ENQUEUE", "kind=" + kind + ";delay=" + delayMs + ";why=" + why);
        return true;
    }

    static PendingIntent alarmPi(Context c, int id, PersistableBundle extras, int flag) {
        Intent i = new Intent(c, AlarmRx.class).setAction("rl.ALARM." + id);
        if (extras != null) for (String k : extras.keySet()) {
            Object o = extras.get(k);
            if (o instanceof Integer) i.putExtra(k, (Integer) o); else if (o != null) i.putExtra(k, o.toString());
        }
        return PendingIntent.getBroadcast(c, id, i, flag | PendingIntent.FLAG_IMMUTABLE);
    }

    /** WorkManager substrate lives in src-work (compiled only into the wm* builds); reached by reflection. */
    static Object bridge(Context c, String m, int id, long delay, PersistableBundle e) {
        try {
            Class<?> k = Class.forName("org.residuelab.WorkBridge");
            return k.getMethod(m, Context.class, int.class, long.class, PersistableBundle.class).invoke(null, c, id, delay, e);
        } catch (Exception x) { throw new RuntimeException(x); }
    }

    public static boolean pending(Context c, int id) {
        if (substrate(c).equals("work")) return (Boolean) bridge(c, "pending", id, 0, null);
        if (substrate(c).equals("alarm")) return alarmPi(c, id, null, PendingIntent.FLAG_NO_CREATE) != null;
        return c.getSystemService(JobScheduler.class).getPendingJob(id) != null;
    }

    public static void cancel(Context c, int id) {
        if (substrate(c).equals("work")) { bridge(c, "cancel", id, 0, null); return; }
        if (substrate(c).equals("alarm")) {
            PendingIntent pi = alarmPi(c, id, null, PendingIntent.FLAG_NO_CREATE);
            if (pi != null) { c.getSystemService(AlarmManager.class).cancel(pi); pi.cancel(); }
        } else c.getSystemService(JobScheduler.class).cancel(id);
    }

    /** cancel-at-withdrawal baseline: cancel the jobs DECLARED in the withdrawn scope and purge its outbox. */
    public static void cancelForWithdrawal(Context c, Model.Tenant t) {
        StringBuilder sb = new StringBuilder();
        int[] kinds = {Model.K_UPLOAD, Model.K_AGG, Model.K_SUMMARY, Model.K_BACKUP, Model.K_PERSONAL};
        for (int k : kinds) {
            if (declaredScope(t, k).equals(t.scope) && t.revokes(purposeOf(t, k))) {
                cancel(c, Model.jobId(t.id, k)); sb.append(k).append(' ');
            }
        }
        android.database.sqlite.SQLiteDatabase d = Db.get(c).getWritableDatabase();
        int purged;
        if (t.dualPurpose) {
            d.execSQL("INSERT OR IGNORE INTO sent(tag,purpose,how) SELECT tag,'personalization',3 FROM records WHERE tenant=?",
                    new Object[]{t.id});
            purged = -1;
        } else {
            purged = d.delete("records", "tenant=? AND tag NOT IN (SELECT tag FROM sent)", new String[]{"" + t.id});
            if (t.summaryDeclared.equals(t.scope)) d.delete("derived", "tenant=?", new String[]{"" + t.id});
        }
        Db.get(c).event(t.id, "CANCEL", "kinds=" + sb.toString().trim() + ";purged=" + purged);
    }

    /** Startup/boot path common in analytics SDKs: if the outbox is non-empty and nothing is scheduled, schedule a flush. */
    public static void resurrect(Context c, String why) {
        Db db = Db.get(c);
        String ts = db.meta("tenants", "");
        if (ts.isEmpty()) return;
        if (substrate(c).equals("work")) return;  // isolate WorkManager's own rescheduling (ForceStopRunnable, reboot)
        long delay = Long.parseLong(db.meta("resurrect_delay", "5000"));
        for (String s : ts.split(",")) {
            Model.Tenant t = Model.TENANTS[Integer.parseInt(s)];
            int[] kinds = t.dualPurpose ? new int[]{Model.K_BACKUP, Model.K_PERSONAL} : new int[]{Model.K_UPLOAD};
            for (int k : kinds) {
                int id = Model.jobId(t.id, k);
                if (unsent(c, t.id, purposeOf(t, k)) > 0 && !pending(c, id)) enqueue(c, t, k, delay, null, why);
            }
            if (t.hasSummary && !pending(c, Model.jobId(t.id, Model.K_SUMMARY))) {
                Cursor cu = db.getReadableDatabase().rawQuery(
                        "SELECT tag, labels, srcs, payload FROM derived WHERE tenant=? AND tag NOT IN (SELECT tag FROM sent)",
                        new String[]{"" + t.id});
                try {
                    if (cu.moveToFirst()) {
                        PersistableBundle e = Work.summaryExtras(c, cu.getString(0), cu.getString(3), cu.getString(2), cu.getString(1));
                        enqueue(c, t, Model.K_SUMMARY, delay, e, why);
                    }
                } finally { cu.close(); }
            }
        }
    }

    static int unsent(Context c, int tenant, String purpose) {
        Cursor cu = Db.get(c).getReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM records WHERE tenant=? AND tag NOT IN (SELECT tag FROM sent WHERE purpose=?)",
                new String[]{"" + tenant, purpose});
        try { cu.moveToFirst(); return cu.getInt(0); } finally { cu.close(); }
    }
}
