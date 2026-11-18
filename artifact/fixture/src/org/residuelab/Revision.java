package org.residuelab;
import android.content.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.residuelab.transport.*;

/** Explicit revision micro-experiment entry, separate from lifecycle campaign commands. */
public class Revision extends BroadcastReceiver {
    static synchronized void event(Context c,String id,String kind,String detail) throws Exception {
        org.json.JSONObject o=new org.json.JSONObject();o.put("v",2);o.put("trial",id);o.put("kind",kind);o.put("detail",detail);
        o.put("mono_ns",android.os.SystemClock.elapsedRealtimeNanos());o.put("pid",android.os.Process.myPid());
        try(FileOutputStream out=new FileOutputStream(new File(c.getFilesDir(),"revision.jsonl"),true)) {out.write((o+"\n").getBytes(StandardCharsets.UTF_8));}
    }
    @Override public void onReceive(Context c0,Intent intent) {
        Context c=c0.getApplicationContext();
        if ("send".equals(intent.getStringExtra("op"))) {
            new Thread(()->{try {run(c,intent);}catch(Exception e){try {event(c,intent.getStringExtra("id"),"SEND_ERROR",e.toString());}catch(Exception ignored){}}}).start();
            setResultData("started");return;
        }
        PendingResult pending=goAsync();
        new Thread(()->{try {run(c,intent);pending.setResultData("ok");}catch(Exception e){pending.setResultData("error:"+e);}
            finally {pending.finish();}}).start();
    }
    static void run(Context c,Intent i)throws Exception {
        String op=i.getStringExtra("op"),id=i.getStringExtra("id");
        if("init".equals(op)) {Policy.initGrants(c);Db.get(c).getWritableDatabase().execSQL("UPDATE grants SET epoch=0,allowed=1");event(c,id,"INITIALIZED","");return;}
        if("withdraw".equals(op)) {
            int tenant=i.getIntExtra("tenant",1);event(c,id,"WITHDRAW_REQUEST","tenant="+tenant);
            try {Coordinator.call(ChunkFence.lock(c),System.nanoTime()+5_000_000_000L,()->{
                android.database.sqlite.SQLiteDatabase d=Db.get(c).getWritableDatabase();d.beginTransaction();
                try {d.execSQL("UPDATE grants SET epoch=epoch+1,allowed=0 WHERE tenant=?",new Object[]{tenant});d.setTransactionSuccessful();}
                finally {d.endTransaction();}event(c,id,"WITHDRAW_DURABLE","tenant="+tenant);return null;});
                event(c,id,"WITHDRAW_ACK","tenant="+tenant);
            }catch(Exception e){event(c,id,"WITHDRAW_TIMEOUT",e.toString());}return;
        }
        if("labelsetup".equals(op)) {
            android.database.sqlite.SQLiteDatabase d=Db.get(c).getWritableDatabase();
            d.execSQL("INSERT OR REPLACE INTO grants(tenant,scope,epoch,allowed) VALUES(1,'diagnostics',0,1)");
            d.execSQL("UPDATE grants SET epoch=1,allowed=0 WHERE tenant=1 AND scope='analytics'");
            event(c,id,"LABEL_SETUP","actual_sources=analytics:0,diagnostics:0;analytics_withdrawn=true");return;
        }
        if("regrant".equals(op)) {Policy.regrant(c,Model.TENANTS[1]);event(c,id,"REGRANTED","");return;}
        if("send".equals(op)) {
            final int size=i.getIntExtra("size",16384),port=i.getIntExtra("port",8794);
            final String mode=i.getStringExtra("mode"),fault=i.getStringExtra("fault");
            final boolean fenced=!"early".equals(mode);final int epoch=i.getIntExtra("epoch",0);
            final String label=i.hasExtra("label")?i.getStringExtra("label"):"analytics:"+epoch;
            String diagnostic=i.getBooleanExtra("labeltest",false)?",\"actual_sources\":[\"analytics:0\",\"diagnostics:0\"],\"derived\":\""+("analytic-value"+"|"+"diagnostic-value")+"\"":"";
            String header="{\"trial\":\""+id+"\",\"source_epoch\":"+epoch+diagnostic+",\"padding\":\"";
            byte[] h=header.getBytes(StandardCharsets.UTF_8);byte[] body=new byte[h.length+size+2];System.arraycopy(h,0,body,0,h.length);Arrays.fill(body,h.length,h.length+size,(byte)'x');body[body.length-2]=(byte)'"';body[body.length-1]=(byte)'}';
            HttpTransport.Policy policy=()->{
                if(label==null||!label.matches("[a-z]+:[0-9]+(,[a-z]+:[0-9]+)*"))return false;
                for(String source:label.split(","))if(Policy.blockedLabel(c,Model.TENANTS[1],source,"analytics",true))return false;
                return true;
            };
            if(!policy.permitted()) {event(c,id,"EARLY_BLOCK","label="+label);return;}
            long started=android.os.SystemClock.elapsedRealtimeNanos(),cpu=android.os.Process.getElapsedCpuTime();
            try {
                HttpTransport.Events trace=(kind,detail)->{
                        event(c,id,kind,detail);
                        if(("afterlog".equals(fault)&&kind.equals("AUTHORIZATION_LOGGED"))||
                           ("unlogged".equals(fault)&&kind.equals("WRITE_RETURN_BOUNDARY"))||
                           ("partial".equals(fault)&&kind.equals("BYTES_ACCEPTED")&&!detail.endsWith("n=0"))||
                           ("response".equals(fault)&&kind.equals("REQUEST_HANDED_OFF")))android.os.Process.killProcess(android.os.Process.myPid());
                        if(("barrier".equals(fault)&&kind.equals("AUTHORIZATION_LOGGED"))||("buffered".equals(fault)&&kind.equals("TLS_BUFFERED")&&detail.contains("record=0;"))) {
                            File release=new File(c.getFilesDir(),"release");long end=System.nanoTime()+4_000_000_000L;
                            while(!release.exists()&&System.nanoTime()<end)Thread.sleep(5);
                            if(!release.exists())throw new IOException("barrier timeout");
                        }
                    };
                if(i.getBooleanExtra("tls",false)) {
                    java.security.KeyStore ks=java.security.KeyStore.getInstance(java.security.KeyStore.getDefaultType());ks.load(null,null);
                    try(InputStream cert=new FileInputStream(new File(c.getFilesDir(),"test-ca.pem"))){ks.setCertificateEntry("test",java.security.cert.CertificateFactory.getInstance("X.509").generateCertificate(cert));}
                    javax.net.ssl.TrustManagerFactory tm=javax.net.ssl.TrustManagerFactory.getInstance(javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm());tm.init(ks);
                    javax.net.ssl.SSLContext ctx=javax.net.ssl.SSLContext.getInstance("TLS");ctx.init(null,tm.getTrustManagers(),null);
                    TlsTransport.post(ctx,i.hasExtra("host")?i.getStringExtra("host"):"10.0.2.2",port,"/ingest/analytics",body,ChunkFence.lock(c),policy,fenced,trace,id,i.getIntExtra("sndbuf",16384),10000);
                } else HttpTransport.postMode(i.hasExtra("host")?i.getStringExtra("host"):"10.0.2.2",port,"/ingest/analytics",body,ChunkFence.lock(c),policy,fenced,"whole".equals(mode),trace,id,i.getIntExtra("attempt",1));
                event(c,id,"SEND_OK","elapsed_ns="+(android.os.SystemClock.elapsedRealtimeNanos()-started)+";process_cpu_ms="+(android.os.Process.getElapsedCpuTime()-cpu)+";payload_bytes="+body.length);
            }catch(Exception e){event(c,id,"SEND_ERROR",e.toString()+";elapsed_ns="+(android.os.SystemClock.elapsedRealtimeNanos()-started)+";process_cpu_ms="+(android.os.Process.getElapsedCpuTime()-cpu));}
        }
    }
}
