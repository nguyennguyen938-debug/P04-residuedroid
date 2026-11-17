package org.residuelab;
import android.content.Context;
import android.os.PersistableBundle;
import android.database.Cursor;
import java.io.*;
import java.util.*;
import org.residuelab.transport.HttpTransport;

/** Revision-only adapter. Historical variants retain their original transport and logs. */
public final class ChunkFence {
    static File lock(Context c) { return new File(c.getFilesDir(), "chunk-policy.lock"); }
    static boolean permitted(Context c, Model.Tenant t, String purpose, String declared, List<Fence.Item> items) {
        for (Fence.Item item : items)
            if (Fence.blockedItem(c, Model.variant(c), t, purpose, declared, item, new Fence.Result())) return false;
        return true;
    }
    static boolean earlyBlocked(Context c, Model.Tenant t, int kind, PersistableBundle ex) {
        List<Fence.Item> items = new ArrayList<>();
        if (kind == Model.K_SUMMARY) {
            items.add(new Fence.Item(ex == null ? "?" : ex.getString("tag"), "derived", "", "",
                ex == null ? null : ex.getString("labels")));
        } else {
            try (Cursor q = Db.get(c).getReadableDatabase().rawQuery("SELECT tag,scope,epoch FROM records WHERE tenant=?", new String[]{""+t.id})) {
                while(q.moveToNext()) items.add(new Fence.Item(q.getString(0), "raw", "", "", q.getString(1)+":"+q.getInt(2)));
            }
        }
        return !permitted(c,t,Sched.purposeOf(t,kind),Sched.declaredScope(t,kind),items);
    }
    static Fence.Result submit(Context c, Model.Tenant t, String purpose, String declared, String job,
                                List<Fence.Item> items, int attempt) throws IOException {
        Fence.Result result = new Fence.Result(); Model.Variant v = Model.variant(c);
        String id = UUID.randomUUID().toString();
        List<Fence.Item> send = items;
        if (v.egressCheck) send = Fence.filter(c,v,t,purpose,declared,items,result);
        if (send.isEmpty()) return result;
        final List<Fence.Item> payload = send;
        byte[] bytes = Fence.encode(t,Fence.body(c,t,purpose,job,id,attempt,"chunk-http",send).replace("SEQ_____________","authorization-v2"));
        try {
            HttpTransport.post(Fence.HOST,Fence.PORT,"/ingest/"+purpose,bytes,lock(c),
                () -> permitted(c,t,purpose,declared,payload),v.egressCheck,
                (kind,detail) -> Db.get(c).event(t.id,kind,"pid="+android.os.Process.myPid()+";trial="+Policy.trial(c)+";job="+job+";"+detail),id,attempt);
            for (Fence.Item it : payload) result.sent.add(it.tag);
        } catch (HttpTransport.Denied e) { for (Fence.Item it : payload) result.blocked.add(it.tag); }
        catch (Exception e) { if (e instanceof IOException) throw (IOException)e; throw new IOException(e); }
        return result;
    }
}
