package org.residuelab;

import android.Manifest;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;

/** Consent/contract state, withdrawal handling, and the per-variant decision rules. */
public final class Policy {
    /** volatile-label ablation: labels kept only in process memory (lost on process death) */
    public static final Map<String, String> MEM_LABELS = new ConcurrentHashMap<>();

    public static String trial(Context c) { return Db.get(c).meta("trial", "t0"); }

    public static void initGrants(Context c) {
        SQLiteDatabase d = Db.get(c).getWritableDatabase();
        for (int i = 1; i < Model.TENANTS.length; i++) {
            Model.Tenant t = Model.TENANTS[i];
            ContentValues v = new ContentValues();
            v.put("tenant", t.id); v.put("scope", t.scope); v.put("epoch", 0); v.put("allowed", 1);
            d.insertWithOnConflict("grants", null, v, SQLiteDatabase.CONFLICT_IGNORE);
        }
    }

    static boolean locationGranted(Context c) {
        return c.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    /** Collect n synthetic tagged records in the tenant's current epoch (if collection is allowed). */
    public static int collect(Context c, Model.Tenant t, int n) {
        Db db = Db.get(c);
        if (t.location && !locationGranted(c)) { db.event(t.id, "COLLECT_DENIED", "os-permission"); return 0; }
        int[] g = db.grant(t.id, t.scope);
        if (g[1] == 0) { db.event(t.id, "COLLECT_SKIPPED", "withdrawn"); return 0; }
        String tr = trial(c);
        Random r = new Random((tr + t.id + g[0]).hashCode());
        SQLiteDatabase d = db.getWritableDatabase();
        int start = countRecords(c, t.id);
        d.beginTransaction();
        try {
            for (int i = 0; i < n; i++) {
                String tag = String.format(Locale.US, "RD-%s-T%d-e%d-%02d", tr, t.id, g[0], start + i);
                ContentValues v = new ContentValues();
                v.put("tag", tag); v.put("tenant", t.id); v.put("scope", t.scope); v.put("epoch", g[0]);
                v.put("payload", "evt=" + tag + ";v=" + r.nextInt(1000)); v.put("t_wall", System.currentTimeMillis());
                d.insert("records", null, v);
                MEM_LABELS.put(tag, t.scope + ":" + g[0]);
            }
            Db.eventTx(d, t.id, "COLLECT", "n=" + n + ";epoch=" + g[0]);
            d.setTransactionSuccessful();
        } finally { d.endTransaction(); }
        return n;
    }

    static int countRecords(Context c, int tenant) {
        Cursor cu = Db.get(c).getReadableDatabase().rawQuery("SELECT COUNT(*) FROM records WHERE tenant=?", new String[]{"" + tenant});
        try { cu.moveToFirst(); return cu.getInt(0); } finally { cu.close(); }
    }

    /** Explicit withdrawal: durable epoch bump, serialized with mediated egress via Fence.LOCK. */
    public static long withdraw(Context c, Model.Tenant t) {
        if (!Model.variant(c).matched) return withdrawLegacy(c, t);
        Db.get(c).event(t.id, "WITHDRAW_REQUEST", "v=2");
        try {
            long seq = org.residuelab.transport.Coordinator.call(ChunkFence.lock(c), System.nanoTime()+5_000_000_000L,
                () -> withdrawLegacy(c, t));
            Db.get(c).event(t.id, "WITHDRAW_ACK", "v=2;withdraw_seq="+seq);
            return seq;
        } catch (Exception e) { Db.get(c).event(t.id, "WITHDRAW_FAILED", e.toString()); throw new IllegalStateException(e); }
    }
    private static long withdrawLegacy(Context c, Model.Tenant t) {
        Db db = Db.get(c);
        long seq;
        synchronized (Fence.LOCK) {
            SQLiteDatabase d = db.getWritableDatabase();
            d.beginTransaction();
            try {
                d.execSQL("UPDATE grants SET epoch=epoch+1, allowed=0 WHERE tenant=? AND scope=?", new Object[]{t.id, t.scope});
                seq = Db.eventTx(d, t.id, "WITHDRAW", t.name);
                if (t.deletes) {
                    int a = d.delete("records", "tenant=?", new String[]{"" + t.id});
                    int b = d.delete("derived", "tenant=?", new String[]{"" + t.id});
                    Db.eventTx(d, t.id, "DELETE_LOCAL", "records=" + a + ";derived=" + b);
                }
                d.setTransactionSuccessful();
            } finally { d.endTransaction(); }
        }
        Model.Variant v = Model.variant(c);
        if (v.cancel && t.revokesPending) Sched.cancelForWithdrawal(c, t);
        Sink.ackAsync(c, t.id, "WITHDRAW", seq);
        return seq;
    }

    public static long regrant(Context c, Model.Tenant t) {
        if (!Model.variant(c).matched) return regrantLegacy(c, t);
        try { return org.residuelab.transport.Coordinator.call(ChunkFence.lock(c), System.nanoTime()+5_000_000_000L,
            () -> regrantLegacy(c, t)); } catch (Exception e) { throw new IllegalStateException(e); }
    }
    private static long regrantLegacy(Context c, Model.Tenant t) {
        Db db = Db.get(c);
        long seq;
        synchronized (Fence.LOCK) {
            SQLiteDatabase d = db.getWritableDatabase();
            d.beginTransaction();
            try {
                d.execSQL("UPDATE grants SET allowed=1 WHERE tenant=? AND scope=?", new Object[]{t.id, t.scope});
                seq = Db.eventTx(d, t.id, "REGRANT", t.name);
                d.setTransactionSuccessful();
            } finally { d.endTransaction(); }
        }
        Sink.ackAsync(c, t.id, "REGRANT", seq);
        return seq;
    }

    /** Conventional check used by cancel/enqueue/job-start/egress-declared baselines:
     *  is the job's DECLARED scope currently withdrawn for this purpose? (boolean, no lineage, no epochs) */
    public static boolean blockedConv(Context c, Model.Tenant t, String declaredScope, String purpose) {
        if (!t.revokes(purpose) || !t.revokesPending) return false;
        int[] g = Db.get(c).grant(t.id, declaredScope);
        return g[1] == 0;
    }

    /** ResidueDroid rule for ONE label (scope:epoch) under the tenant's stated contract. */
    public static boolean blockedLabel(Context c, Model.Tenant t, String label, String purpose, boolean contractAware) {
        if (Model.variant(c).matched && (label == null || !label.matches("[a-z]+:[0-9]+"))) return true;
        int k = label.lastIndexOf(':');
        String scope = label.substring(0, k);
        int ep = Integer.parseInt(label.substring(k + 1));
        int[] g = Db.get(c).grant(t.id, scope);
        if (Model.variant(c).matched && (g[0] < 0 || ep > g[0])) return true;
        if (!contractAware) {
            // generic taint rule: any withdrawal (or OS revocation) of the source taints all purposes, all epochs
            if (t.location && !locationGranted(c)) return true;
            return g[0] > ep || g[1] == 0;
        }
        if (!t.revokes(purpose)) return false;
        if (t.revokesPending && ep < g[0]) return true;
        return ep == g[0] && g[1] == 0;
    }
}
