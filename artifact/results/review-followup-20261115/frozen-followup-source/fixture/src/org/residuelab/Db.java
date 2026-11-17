package org.residuelab;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.SystemClock;

/**
 * Durable app state. records/derived rows carry their provenance label (scope, epoch / label set)
 * in the SAME row, so a label is committed atomically with the data it describes.
 * events is the fixture's oracle log: one global, persistent sequence shared by withdrawals and
 * pre-write authorization and revision write observations (not enforcement inputs).
 */
public final class Db extends SQLiteOpenHelper {
    private final boolean strict;
    private static Db inst;
    public static synchronized Db get(Context c) {
        if (inst == null) inst = new Db(c.getApplicationContext());
        return inst;
    }
    private Db(Context c) { super(c, "rl.db", null, 3); strict = Model.variant(c).matched; setWriteAheadLoggingEnabled(true); }

    @Override public void onCreate(SQLiteDatabase d) {
        d.execSQL("CREATE TABLE records(tag TEXT PRIMARY KEY, tenant INT, scope TEXT, epoch INT, payload TEXT, t_wall INT)");
        d.execSQL("CREATE TABLE derived(tag TEXT PRIMARY KEY, tenant INT, labels TEXT, srcs TEXT, payload TEXT, t_wall INT)");
        d.execSQL("CREATE TABLE sent(tag TEXT, purpose TEXT, how INT, PRIMARY KEY(tag,purpose))");
        d.execSQL("CREATE TABLE grants(tenant INT, scope TEXT, epoch INT, allowed INT, PRIMARY KEY(tenant,scope))");
        d.execSQL("CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, t_wall INT, t_el INT, tenant INT, kind TEXT, detail TEXT)");
        d.execSQL("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)");
        d.execSQL("CREATE TABLE bench(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT, labels TEXT)");
        d.execSQL("CREATE TABLE bench_nolabel(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT)");
        d.execSQL("CREATE TABLE crash(id INTEGER PRIMARY KEY, payload TEXT, labels TEXT)");
        d.execSQL("CREATE TABLE crashb(id INTEGER PRIMARY KEY, payload TEXT)");
    }
    @Override public void onUpgrade(SQLiteDatabase d, int a, int b) {}

    public synchronized long event(int tenant, String kind, String detail) {
        ContentValues v = new ContentValues();
        v.put("t_wall", System.currentTimeMillis());
        v.put("t_el", SystemClock.elapsedRealtime());
        v.put("tenant", tenant); v.put("kind", kind); v.put("detail", detail);
        return getWritableDatabase().insert("events", null, v);
    }
    /** event inside an existing transaction on d */
    public static long eventTx(SQLiteDatabase d, int tenant, String kind, String detail) {
        ContentValues v = new ContentValues();
        v.put("t_wall", System.currentTimeMillis());
        v.put("t_el", SystemClock.elapsedRealtime());
        v.put("tenant", tenant); v.put("kind", kind); v.put("detail", detail);
        return d.insert("events", null, v);
    }
    public synchronized void putMeta(String k, String v) {
        ContentValues cv = new ContentValues(); cv.put("k", k); cv.put("v", v);
        getWritableDatabase().insertWithOnConflict("meta", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }
    public synchronized String meta(String k, String def) {
        Cursor c = getReadableDatabase().rawQuery("SELECT v FROM meta WHERE k=?", new String[]{k});
        try { return c.moveToFirst() ? c.getString(0) : def; } finally { c.close(); }
    }
    /** grant state: int[]{epoch, allowed}; absent scope = never granted-and-withdrawable => {0,1} */
    public synchronized int[] grant(int tenant, String scope) {
        Cursor c = getReadableDatabase().rawQuery("SELECT epoch, allowed FROM grants WHERE tenant=? AND scope=?",
                new String[]{"" + tenant, scope});
        try { return c.moveToFirst() ? new int[]{c.getInt(0), c.getInt(1)} : (strict ? new int[]{-1, 0} : new int[]{0, 1}); } finally { c.close(); }
    }
}
