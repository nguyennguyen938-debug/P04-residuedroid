package org.residuelab;

import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Parcel;
import android.os.PersistableBundle;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** On-device micro-experiments: overhead, serialization race, label durability under SIGKILL. */
public final class Bench {
    static long ns() { return SystemClock.elapsedRealtimeNanos(); }

    static JSONArray arr(long[] a) { JSONArray j = new JSONArray(); for (long x : a) j.put(x); return j; }

    public static void overhead(Context c, int n) {
        try {
            Db db = Db.get(c);
            SQLiteDatabase d = db.getWritableDatabase();
            Model.Variant v = Model.variant(c);
            Policy.initGrants(c);
            long[] insNo = new long[n], insLab = new long[n], decNone = new long[n], decConv = new long[n], decRd = new long[n];
            long[] e2e = new long[Math.min(n, 300)];
            Model.Tenant t = Model.TENANTS[1];
            for (int i = 0; i < n; i++) {
                String p = "evt=bench-" + i + ";v=" + (i % 997);
                long a = ns();
                ContentValues cv = new ContentValues(); cv.put("payload", p);
                d.insert("bench_nolabel", null, cv);
                long b = ns();
                ContentValues cl = new ContentValues(); cl.put("payload", p); cl.put("labels", "analytics:0");
                d.insert("bench", null, cl);
                long e = ns();
                insNo[i] = b - a; insLab[i] = e - b;
            }
            List<Fence.Item> batch = new ArrayList<>();
            for (int k = 0; k < Work.BATCH; k++) batch.add(new Fence.Item("RD-bench-" + k, "raw", "", "evt", "analytics:0"));
            Model.Variant conv = new Model.Variant("x"); conv.egressCheck = true;
            Model.Variant rd = new Model.Variant("y"); rd.egressCheck = true; rd.lineage = true; rd.durable = true; rd.contractAware = true;
            for (int i = 0; i < n; i++) {
                long a = ns();
                synchronized (Fence.LOCK) { db.event(t.id, "BENCH_COMMIT", "none"); }
                long b = ns();
                synchronized (Fence.LOCK) { Fence.filter(c, conv, t, "analytics", "analytics", batch, new Fence.Result()); db.event(t.id, "BENCH_COMMIT", "conv"); }
                long e = ns();
                synchronized (Fence.LOCK) { Fence.filter(c, rd, t, "analytics", "analytics", batch, new Fence.Result()); db.event(t.id, "BENCH_COMMIT", "rd"); }
                long f = ns();
                decNone[i] = b - a; decConv[i] = e - b; decRd[i] = f - e;
            }
            // job-extras size with and without the label
            PersistableBundle plain = Work.summaryExtras(c, "RD-x-T1-sum-12", "count=12;sum=6000;srcs=" + srcs(12), srcs(12), null);
            plain.remove("labels");
            PersistableBundle lab = new PersistableBundle(plain); lab.putString("labels", "analytics:0");
            int szPlain = parcelSize(plain), szLab = parcelSize(lab);
            // end-to-end mediated submission of one 4-item batch through this package's own variant
            Db.get(c).putMeta("trial", "bench");
            for (int i = 0; i < e2e.length; i++) {
                long a = ns();
                try { Fence.submit(c, t, "bench", "analytics", "bench", batch, 1); } catch (Exception ex) { }
                e2e[i] = ns() - a;
            }
            JSONObject o = new JSONObject();
            o.put("pkg", c.getPackageName()); o.put("variant", v.name); o.put("n", n);
            o.put("ins_nolabel_ns", arr(insNo)); o.put("ins_label_ns", arr(insLab));
            o.put("commit_none_ns", arr(decNone)); o.put("commit_conv_ns", arr(decConv)); o.put("commit_rd_ns", arr(decRd));
            o.put("e2e_ns", arr(e2e)); o.put("extras_plain_bytes", szPlain); o.put("extras_label_bytes", szLab);
            Sink.post("/bench", o.toString());
        } catch (Exception e) { Sink.post("/bench", "{\"error\":\"" + e + "\"}"); }
    }

    static String srcs(int n) { StringBuilder sb = new StringBuilder(); for (int i = 0; i < n; i++) { if (i > 0) sb.append('|'); sb.append(String.format("RD-t0000-T1-e0-%02d", i)); } return sb.toString(); }
    static int parcelSize(PersistableBundle b) { Parcel p = Parcel.obtain(); p.writePersistableBundle(b); int s = p.dataSize(); p.recycle(); return s; }

    /** Serialization race: a submitter loop vs a withdrawal at a random offset. A violation is a COMMIT of an
     *  epoch-0 item whose sequence number is greater than the withdrawal's. */
    public static void stress(Context c, int rounds, long delay, int maxOff) {
        try {
            Db db = Db.get(c);
            Model.Variant v = Model.variant(c);
            v.raceDelayMs = delay;
            db.putMeta("trial", "stress");
            Policy.initGrants(c);
            final Model.Tenant t = Model.TENANTS[1];
            Random rnd = new Random(1234 + delay * 7 + (v.serialize ? 1 : 0));
            int viol = 0, totalLate = 0; long[] lateCounts = new long[rounds];
            for (int r = 0; r < rounds; r++) {
                SQLiteDatabase d = db.getWritableDatabase();
                synchronized (Fence.LOCK) { d.execSQL("UPDATE grants SET epoch=0, allowed=1 WHERE tenant=1"); }
                long startSeq = db.event(1, "STRESS_ROUND", "r=" + r);
                final List<Fence.Item> one = new ArrayList<>();
                one.add(new Fence.Item("RD-stress-" + r, "raw", "", "evt", "analytics:0"));
                final boolean[] stop = {false};
                Thread sub = new Thread(() -> {
                    int k = 0;
                    while (!stop[0] && k < 400) {
                        try { Fence.Result res = Fence.submit(c, t, "stress", "analytics", "stress", one, 1); if (res.sent.isEmpty()) break; }
                        catch (Exception e) { }
                        k++;
                    }
                });
                sub.start();
                Fence.sleep(rnd.nextInt(maxOff + 1));
                long w;
                synchronized (Fence.LOCK) {
                    d.beginTransaction();
                    try { d.execSQL("UPDATE grants SET epoch=1, allowed=0 WHERE tenant=1"); w = Db.eventTx(d, 1, "WITHDRAW", "stress"); d.setTransactionSuccessful(); }
                    finally { d.endTransaction(); }
                }
                Fence.sleep(Math.max(60, delay * 3));
                stop[0] = true;
                sub.join();
                Cursor cu = d.rawQuery("SELECT COUNT(*) FROM events WHERE kind='COMMIT' AND seq>? AND detail LIKE 'job=stress%'", new String[]{"" + w});
                int late; try { cu.moveToFirst(); late = cu.getInt(0); } finally { cu.close(); }
                lateCounts[r] = late; totalLate += late; if (late > 0) viol++;
                d.execSQL("DELETE FROM events WHERE seq>=?", new Object[]{startSeq});
            }
            JSONObject o = new JSONObject();
            o.put("pkg", c.getPackageName()); o.put("variant", v.name); o.put("delay_ms", delay); o.put("rounds", rounds);
            o.put("maxoff_ms", maxOff); o.put("violating_rounds", viol); o.put("late_commits", totalLate); o.put("late_per_round", arr(lateCounts));
            Sink.post("/stress", o.toString());
        } catch (Exception e) { Sink.post("/stress", "{\"error\":\"" + e + "\"}"); }
    }

    /** Durability: write derived rows forever (killed by the harness). Design A: label in the same row/transaction.
     *  Design B: row in SQLite, label afterwards in SharedPreferences (separate store). */
    public static void crashWrite(Context c) {
        SQLiteDatabase d = Db.get(c).getWritableDatabase();
        SharedPreferences sp = c.getSharedPreferences("labels_b", Context.MODE_PRIVATE);
        Cursor cu = d.rawQuery("SELECT COALESCE(MAX(id),0) FROM crash", null);
        long id; try { cu.moveToFirst(); id = cu.getLong(0) + 1; } finally { cu.close(); }
        while (true) {
            ContentValues a = new ContentValues(); a.put("id", id); a.put("payload", "sum-" + id); a.put("labels", "analytics:0");
            d.insert("crash", null, a);                       // design A: one atomic row insert
            ContentValues b = new ContentValues(); b.put("id", id); b.put("payload", "sum-" + id);
            d.insert("crashb", null, b);                      // design B: data first ...
            sp.edit().putString("l" + id, "analytics:0").commit(); // ... label second, separate store
            id++;
        }
    }

    public static String crashCheck(Context c) {
        SQLiteDatabase d = Db.get(c).getWritableDatabase();
        SharedPreferences sp = c.getSharedPreferences("labels_b", Context.MODE_PRIVATE);
        int rowsA = 0, orphanA = 0, rowsB = 0, orphanB = 0;
        Cursor cu = d.rawQuery("SELECT labels FROM crash", null);
        try { while (cu.moveToNext()) { rowsA++; if (cu.isNull(0)) orphanA++; } } finally { cu.close(); }
        cu = d.rawQuery("SELECT id FROM crashb", null);
        try { while (cu.moveToNext()) { rowsB++; if (!sp.contains("l" + cu.getLong(0))) orphanB++; } } finally { cu.close(); }
        // repair B orphans so that each kill is counted independently
        cu = d.rawQuery("SELECT id FROM crashb", null);
        SharedPreferences.Editor ed = sp.edit();
        try { while (cu.moveToNext()) if (!sp.contains("l" + cu.getLong(0))) ed.putString("l" + cu.getLong(0), "repaired"); } finally { cu.close(); }
        ed.commit();
        return "rowsA=" + rowsA + ";orphanA=" + orphanA + ";rowsB=" + rowsB + ";orphanB=" + orphanB;
    }
}
