package org.residuelab;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.PersistableBundle;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;

/** Body of every deferred job (shared by the JobScheduler and AlarmManager substrates). */
public final class Work {
    public static final int BATCH = 4, MAX_ATTEMPTS = 5;
    public interface Ctl { boolean stopped(); }

    public static PersistableBundle summaryExtras(Context c, String tag, String payload, String srcs, String labels) {
        PersistableBundle e = new PersistableBundle();
        e.putString("tag", tag); e.putString("payload", payload); e.putString("srcs", srcs);
        Model.Variant v = Model.variant(c);
        if (v.lineage && v.durable) e.putString("labels", labels); // label rides in the job's own persisted input
        return e;
    }

    /** @return true if the job should be rescheduled (network failure after all attempts) */
    public static boolean run(Context c, int tenantId, int kind, PersistableBundle ex, Ctl ctl) {
        Model.Tenant t = Model.TENANTS[tenantId];
        Model.Variant v = Model.variant(c);
        Db db = Db.get(c);
        String job = Model.jobId(tenantId, kind) + "";
        db.event(t.id, "JOBSTART", "kind=" + kind);
        maybeInject(c, t, kind);
        String declared = Sched.declaredScope(t, kind), purpose = Sched.purposeOf(t, kind);
        if (v.jobStartCheck && (v.matched ? ChunkFence.earlyBlocked(c,t,kind,ex) : Policy.blockedConv(c, t, declared, purpose))) {
            db.event(t.id, "JOB_SKIP", "kind=" + kind);
            return false;
        }
        if (kind == Model.K_AGG) { aggregate(c, t); return false; }

        List<Fence.Item> items = new ArrayList<>();
        if (kind == Model.K_SUMMARY) {
            String tag = ex.getString("tag");
            if (tag == null || isSent(c, tag, purpose)) return false;
            items.add(new Fence.Item(tag, "derived", ex.getString("srcs"), ex.getString("payload"), ex.getString("labels")));
        } else {
            Cursor cu = db.getReadableDatabase().rawQuery(
                    "SELECT tag, scope, epoch, payload FROM records WHERE tenant=? AND tag NOT IN " +
                            "(SELECT tag FROM sent WHERE purpose=?) ORDER BY tag", new String[]{"" + t.id, purpose});
            try {
                while (cu.moveToNext())
                    items.add(new Fence.Item(cu.getString(0), "raw", "", cu.getString(3), cu.getString(1) + ":" + cu.getInt(2)));
            } finally { cu.close(); }
        }
        db.event(t.id, "PREPARED", "kind=" + kind + ";n=" + items.size());
        for (int i = 0; i < items.size(); i += BATCH) {
            if (ctl != null && ctl.stopped()) { db.event(t.id, "JOB_STOPPED", "kind=" + kind + ";at=" + i); return false; }
            List<Fence.Item> batch = items.subList(i, Math.min(items.size(), i + BATCH));
            boolean ok = false;
            for (int a = 1; a <= MAX_ATTEMPTS && !ok; a++) {
                try {
                    if (v.retryCheck && !ChunkFence.permitted(c,t,purpose,declared,batch)) {
                        db.event(t.id,"RETRY_ENTRY_BLOCK","attempt="+a); ok=true; continue;
                    }
                    if (t.unmediated) {
                        Fence.rawSend(c, t, purpose, job, batch, a);
                        for (Fence.Item it : batch) mark(c, it.tag, purpose, 1);
                    } else {
                        Fence.Result r = Fence.submit(c, t, purpose, declared, job, batch, a);
                        for (String s : r.sent) mark(c, s, purpose, 1);
                        for (String s : r.blocked) mark(c, s, purpose, 2);
                    }
                    ok = true;
                } catch (IOException e) {
                    db.event(t.id, "NET_FAIL", "kind=" + kind + ";attempt=" + a + ";err=" + e.getClass().getSimpleName());
                    if (a < MAX_ATTEMPTS) Fence.sleep(1000L << (a - 1));
                }
            }
            if (!ok) { db.event(t.id, "JOB_RETRY_LATER", "kind=" + kind); return true; }
        }
        db.event(t.id, "JOBDONE", "kind=" + kind);
        return false;
    }

    public static void aggregate(Context c, Model.Tenant t) {
        Db db = Db.get(c);
        SQLiteDatabase d = db.getWritableDatabase();
        List<String> tags = new ArrayList<>();
        TreeSet<String> labels = new TreeSet<>();
        int sum = 0;
        Cursor cu = d.rawQuery("SELECT tag, scope, epoch, payload FROM records WHERE tenant=? ORDER BY tag", new String[]{"" + t.id});
        try {
            while (cu.moveToNext()) {
                tags.add(cu.getString(0)); labels.add(cu.getString(1) + ":" + cu.getInt(2));
                String p = cu.getString(3); sum += Integer.parseInt(p.substring(p.indexOf(";v=") + 3));
            }
        } finally { cu.close(); }
        if (tags.isEmpty()) { db.event(t.id, "AGG_EMPTY", ""); return; }
        String tag = String.format(Locale.US, "RD-%s-T%d-sum-%02d", Policy.trial(c), t.id, tags.size());
        String srcs = String.join("|", tags);
        String lab = String.join(",", labels);
        String payload = "count=" + tags.size() + ";sum=" + sum + ";srcs=" + srcs;
        d.beginTransaction();
        try {
            ContentValues v = new ContentValues();
            v.put("tag", tag); v.put("tenant", t.id); v.put("labels", lab); v.put("srcs", srcs); v.put("payload", payload);
            v.put("t_wall", System.currentTimeMillis());
            d.insertWithOnConflict("derived", null, v, SQLiteDatabase.CONFLICT_REPLACE);
            Db.eventTx(d, t.id, "AGG", "tag=" + tag + ";labels=" + lab);
            d.setTransactionSuccessful();
        } finally { d.endTransaction(); }
        Policy.MEM_LABELS.put(tag, lab);
        long sd = Long.parseLong(db.meta("sum_delay", "15000"));
        Sched.enqueue(c, t, Model.K_SUMMARY, sd, summaryExtras(c, tag, payload, srcs, lab), "aggregator");
    }

    static boolean isSent(Context c, String tag, String purpose) {
        Cursor cu = Db.get(c).getReadableDatabase().rawQuery("SELECT 1 FROM sent WHERE tag=? AND purpose=?", new String[]{tag, purpose});
        try { return cu.moveToFirst(); } finally { cu.close(); }
    }
    static void mark(Context c, String tag, String purpose, int how) {
        ContentValues v = new ContentValues(); v.put("tag", tag); v.put("purpose", purpose); v.put("how", how);
        Db.get(c).getWritableDatabase().insertWithOnConflict("sent", null, v, SQLiteDatabase.CONFLICT_IGNORE);
    }

    /** Fault injection for in-flight/net-loss schedules: one-shot withdrawal at a seeded offset after the job starts. */
    static void maybeInject(final Context c, final Model.Tenant t, int kind) {
        int trig = t.dualPurpose ? Model.K_PERSONAL : Model.K_UPLOAD;
        if (kind != trig) return;
        final Db db = Db.get(c);
        String key = "inj_" + t.id;
        final String off;
        synchronized (Work.class) {
            off = db.meta(key, "");
            if (off.isEmpty()) return;
            db.putMeta(key, "");
        }
        db.event(t.id, "INJECT_ARMED", "offset_ms=" + off);
        new Thread(() -> {
            Fence.sleep(Long.parseLong(off));
            Cmd.doWithdraw(c, t);
        }).start();
    }
}
