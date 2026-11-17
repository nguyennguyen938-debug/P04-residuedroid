package org.residuelab.acra;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.residuelab.transport.Coordinator;

/** Transactional state; never infer permission from an absent/corrupt state file. */
public final class Fence {
    static File f(Context c,String n) { return new File(c.getFilesDir(),n); }
    public static File lockFile(Context c) { return f(c,"rd_fence.lock"); }
    public interface Body { void run(int epoch,int allowed) throws Exception; }
    public static void locked(Context c,Body body) throws Exception {
        Coordinator.call(lockFile(c),System.nanoTime()+5_000_000_000L,() -> { int[] s=read(c);body.run(s[0],s[1]);return null; });
    }
    private static SQLiteDatabase open(Context c) { return SQLiteDatabase.openDatabase(f(c,"rd_policy.db").getPath(),null,SQLiteDatabase.OPEN_READWRITE); }
    public static void initialize(Context c) throws Exception {
        Coordinator.call(lockFile(c),System.nanoTime()+5_000_000_000L,() -> {
            if(f(c,"rd_policy.db").exists() || f(c,"rd_initialized").exists()) return null;
            // Marker precedes creation: interrupted initialization fails closed on the next start.
            try(FileOutputStream marker=new FileOutputStream(f(c,"rd_initialized"))) { marker.write(1);marker.getFD().sync(); }
            int ep=0, allowed=1;
            File legacy=f(c,"rd_epoch");
            if(legacy.exists()) {
                try { String[] p=new String(Files.readAllBytes(legacy.toPath()),StandardCharsets.UTF_8).trim().split(" ");
                    ep=Integer.parseInt(p[0]);allowed=Integer.parseInt(p[1]);
                    if(p.length!=2||ep<0||(allowed!=0&&allowed!=1))throw new IOException("legacy state");
                } catch(Exception e) { ep=-1;allowed=0;log(c,"MIGRATION_FAIL_CLOSED"); }
            } else {
                String[] a=c.getDir("ACRA-approved",0).list(),u=c.getDir("ACRA-unapproved",0).list();
                if ((a!=null&&a.length>0)||(u!=null&&u.length>0)) { ep=-1;allowed=0;log(c,"LEGACY_REPORTS_NO_POLICY"); }
            }
            if(ep<0)throw new IOException("untrusted legacy policy requires explicit repair");
            try(SQLiteDatabase d=SQLiteDatabase.openOrCreateDatabase(f(c,"rd_policy.db"),null)) {
                d.execSQL("PRAGMA synchronous=FULL");d.beginTransaction();
                try { d.execSQL("CREATE TABLE policy(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL CHECK(epoch>=0),allowed INTEGER NOT NULL CHECK(allowed IN (0,1)))");
                    d.execSQL("INSERT INTO policy VALUES(1,?,?)",new Object[]{ep,allowed});d.setTransactionSuccessful();
                } finally {d.endTransaction();}
            }
            if(!c.getSharedPreferences(c.getPackageName()+"_preferences",0).edit().putBoolean(org.acra.ACRA.PREF_ENABLE_ACRA,allowed==1).commit())throw new IOException("initial preference save failed");
            return null;
        });
    }
    public static int[] read(Context c) {
        try(SQLiteDatabase d=open(c);Cursor q=d.rawQuery("SELECT epoch,allowed FROM policy WHERE id=1",null)) {
            if(!q.moveToFirst())throw new IOException("missing row");
            int ep=q.getInt(0),a=q.getInt(1); if(ep<0||(a!=0&&a!=1))throw new IOException("invalid state");return new int[]{ep,a};
        } catch(Exception e) { log(c,"POLICY_UNAVAILABLE error="+e.getClass().getSimpleName());return new int[]{-1,0}; }
    }
    public static void write(Context c,int epoch,int allowed) throws Exception {
        if(epoch<0)throw new IOException("invalid epoch");
        try(SQLiteDatabase d=open(c)) { d.execSQL("PRAGMA synchronous=FULL");d.beginTransaction();
            try { d.execSQL("UPDATE policy SET epoch=?,allowed=? WHERE id=1",new Object[]{epoch,allowed});d.setTransactionSuccessful(); }
            finally { d.endTransaction(); }
        }
    }
    public static void setEnabled(Context c,boolean enabled) throws Exception {
        log(c,enabled?"REGRANT_REQUEST":"WITHDRAW_REQUEST");
        locked(c,(epoch,allowed)-> {
            if(epoch<0)throw new IOException("policy unavailable");
            write(c,enabled?epoch:epoch+1,enabled?1:0);log(c,enabled?"REGRANT_DURABLE":"WITHDRAW_DURABLE");
            boolean saved=c.getSharedPreferences(c.getPackageName()+"_preferences",0).edit().putBoolean(org.acra.ACRA.PREF_ENABLE_ACRA,enabled).commit();
            if(!saved)throw new IOException("ACRA preference commit failed; policy already updated");
        });
        log(c,enabled?"REGRANT_ACK":"WITHDRAW_ACK");
    }
    public static synchronized void log(Context c,String line) {
        try(FileOutputStream o=new FileOutputStream(f(c,"rd_events.log"),true)) {
            o.write((System.currentTimeMillis()+" mono="+android.os.SystemClock.elapsedRealtimeNanos()+" pid="+android.os.Process.myPid()+" "+line+"\n").getBytes(StandardCharsets.UTF_8));
        } catch(Exception ignored) {} // audit loss is an unknown outcome, not evidence of zero handoff
    }
}
