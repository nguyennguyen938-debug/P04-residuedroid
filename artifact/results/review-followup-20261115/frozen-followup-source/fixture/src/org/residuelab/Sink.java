package org.residuelab;

import android.content.Context;
import android.database.Cursor;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Measurement control channel (NOT application egress): withdrawal acks, end-of-trial reports, bench results. */
public final class Sink {
    public static boolean post(String path, String body) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL("http://" + Fence.HOST + ":" + Fence.PORT + path).openConnection();
            c.setConnectTimeout(3000); c.setReadTimeout(20000); c.setDoOutput(true); c.setRequestMethod("POST");
            byte[] b = body.getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(b.length);
            OutputStream os = c.getOutputStream(); os.write(b); os.flush();
            int code = c.getResponseCode();
            InputStream is = c.getInputStream(); while (is.read() >= 0) { } is.close();
            c.disconnect();
            return code == 200;
        } catch (Exception e) { return false; }
    }
    public static void ackAsync(Context c, int tenant, String kind, long seq) {
        final String b = "{\"pkg\":\"" + c.getPackageName() + "\",\"trial\":\"" + Policy.trial(c) + "\",\"tenant\":" + tenant
                + ",\"kind\":\"" + kind + "\",\"seq\":" + seq + ",\"t_dev\":" + System.currentTimeMillis() + "}";
        new Thread(() -> post("/ack", b)).start();
    }
    public static boolean report(Context c) {
        try {
            Db db = Db.get(c);
            JSONObject o = new JSONObject();
            o.put("pkg", c.getPackageName()); o.put("variant", Model.variant(c).name); o.put("trial", Policy.trial(c));
            JSONArray ev = new JSONArray();
            Cursor cu = db.getReadableDatabase().rawQuery("SELECT seq,t_wall,t_el,tenant,kind,detail FROM events ORDER BY seq", null);
            try {
                while (cu.moveToNext()) {
                    JSONArray r = new JSONArray();
                    r.put(cu.getLong(0)); r.put(cu.getLong(1)); r.put(cu.getLong(2)); r.put(cu.getInt(3)); r.put(cu.getString(4)); r.put(cu.getString(5));
                    ev.put(r);
                }
            } finally { cu.close(); }
            o.put("events", ev);
            JSONArray pend = new JSONArray();
            for (android.app.job.JobInfo j : c.getSystemService(android.app.job.JobScheduler.class).getAllPendingJobs()) pend.put(j.getId());
            o.put("pending_jobs", pend);
            JSONArray rows = new JSONArray();
            cu = db.getReadableDatabase().rawQuery("SELECT tenant, COUNT(*) FROM records GROUP BY tenant", null);
            try { while (cu.moveToNext()) rows.put(cu.getInt(0) + ":" + cu.getInt(1)); } finally { cu.close(); }
            o.put("residual_records", rows);
            JSONArray drows = new JSONArray();
            cu = db.getReadableDatabase().rawQuery("SELECT tenant, COUNT(*) FROM derived GROUP BY tenant", null);
            try { while (cu.moveToNext()) drows.put(cu.getInt(0) + ":" + cu.getInt(1)); } finally { cu.close(); }
            o.put("residual_derived", drows);
            return post("/report", o.toString());
        } catch (Exception e) { return false; }
    }
}
