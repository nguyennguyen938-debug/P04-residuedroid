package org.residuelab.matomo;
import android.content.*;import android.database.*;import android.database.sqlite.*;
import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;import java.net.*;
import org.matomo.sdk.*;import org.matomo.sdk.dispatcher.*;import org.matomo.sdk.tools.Connectivity;
import org.residuelab.transport.*;

/** Real Matomo 4.4 dispatcher/cache with a PacketSender adapter; controlled barrier is test-only. */
public class Cmd extends BroadcastReceiver {
 static Tracker tracker;static Dispatcher dispatcher;static String trial;static boolean fenced;
 static File file(Context c,String n){return new File(c.getFilesDir(),n);}
 static SQLiteDatabase db(Context c){return SQLiteDatabase.openDatabase(file(c,"policy.db").getPath(),null,SQLiteDatabase.OPEN_READWRITE);}
 static int[] state(Context c){try(SQLiteDatabase d=db(c);Cursor q=d.rawQuery("SELECT epoch,allowed FROM policy",null)){if(q.moveToFirst())return new int[]{q.getInt(0),q.getInt(1)};}catch(Exception ignored){}return new int[]{-1,0};}
 static synchronized void log(Context c,String s){try(FileOutputStream o=new FileOutputStream(file(c,"events.log"),true)){o.write((android.os.SystemClock.elapsedRealtimeNanos()+" "+s+"\n").getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){}}
 static void setup(Context c,String id,boolean fence)throws Exception {
  trial=id;fenced=fence;
  if(!file(c,"policy.db").exists())try(SQLiteDatabase d=SQLiteDatabase.openOrCreateDatabase(file(c,"policy.db"),null)){d.execSQL("CREATE TABLE policy(epoch INT,allowed INT)");d.execSQL("INSERT INTO policy VALUES(0,1)");}
  Matomo matomo=Matomo.getInstance(c);
  matomo.setDispatcherFactory(t->{
   PacketSender sender=new PacketSender(){
    DefaultPacketSender stock=new DefaultPacketSender();
    public void setTimeout(long n){stock.setTimeout(n);}public void setGzipData(boolean b){stock.setGzipData(b);}
    public boolean send(Packet packet){
     try {
      log(c,"PRE_SEND trial="+trial+" events="+packet.getEventCount());
      long until=System.nanoTime()+10_000_000_000L;while(!file(c,"release").exists()&&System.nanoTime()<until)Thread.sleep(5);
      if(!file(c,"release").exists())throw new IOException("barrier not released");
      if(!fenced)return stock.send(packet);
      org.json.JSONObject body=packet.getPostData();
      if(body==null){body=new org.json.JSONObject();body.put("requests",new org.json.JSONArray().put("?"+new URI(packet.getTargetURL()).getRawQuery()));}
      org.json.JSONArray requests=body.getJSONArray("requests");final List<Integer> epochs=new ArrayList<>();
      for(int j=0;j<requests.length();j++){
       String query=requests.getString(j);Integer ep=null;
       for(String pair:query.replaceFirst("^\\?","").split("&")){String[] kv=pair.split("=",2);if(kv.length==2&&URLDecoder.decode(kv[0],"UTF-8").equals("rd_epoch"))ep=Integer.valueOf(URLDecoder.decode(kv[1],"UTF-8"));}
       if(ep==null||ep<0){log(c,"BLOCK missing_label");return true;}epochs.add(ep);
      }
      HttpTransport.post("10.0.2.2",8798,"/ingest/analytics",body.toString().getBytes(StandardCharsets.UTF_8),file(c,"policy.lock"),
       ()->{int[] s=state(c);if(s[0]<0||s[1]!=1)return false;for(int ep:epochs)if(ep!=s[0])return false;return true;},true,
       (kind,detail)->log(c,kind+" "+detail),UUID.randomUUID().toString(),1);
      return true;
     }catch(HttpTransport.Denied e){log(c,"BLOCK withdrawn");return true;}catch(Exception e){log(c,"SEND_ERROR "+e);return false;}
    }
   };
   dispatcher=new DefaultDispatcher(new EventCache(new EventDiskCache(t)),new Connectivity(c),new PacketFactory(t.getAPIUrl()),sender);return dispatcher;
  });
  tracker=TrackerBuilder.createDefault("http://10.0.2.2:8798/ingest/analytics",1).build(matomo);tracker.setDispatchInterval(-1);
 }
 @Override public void onReceive(Context ctx,Intent i){Context c=ctx.getApplicationContext();try{
  String op=i.getStringExtra("op");
  if("setup".equals(op)){setup(c,i.getStringExtra("trial"),i.getBooleanExtra("fenced",true));for(int j=0;j<2;j++)tracker.track(new TrackMe().set("action_name",trial+"-"+j).set("rd_epoch","0"));setResultData("queued");}
  else if("dispatch".equals(op)){dispatcher.forceDispatch();setResultData("dispatching");}
  else if("withdraw".equals(op)){Coordinator.call(file(c,"policy.lock"),System.nanoTime()+5_000_000_000L,()->{try(SQLiteDatabase d=db(c)){d.beginTransaction();try{d.execSQL("UPDATE policy SET epoch=epoch+1,allowed=0");d.setTransactionSuccessful();}finally{d.endTransaction();}}tracker.setOptOut(true);log(c,"WITHDRAW_ACK");return null;});setResultData("withdrawn");}
  else if("release".equals(op)){file(c,"release").createNewFile();setResultData("released");}
 }catch(Exception e){log(c,"ERROR "+e);setResultData("error "+e);}}
}
