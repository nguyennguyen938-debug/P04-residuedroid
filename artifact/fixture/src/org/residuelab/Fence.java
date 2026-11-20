package org.residuelab;

import android.content.Context;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Socket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * Historical stream wrapper retained for original variants. Its COMMIT log precedes
 * getOutputStream/write and is an authorization marker, not observed socket acceptance.
 * Revision variants delegate to ChunkFence and the audited nonblocking transport.
 */
public final class Fence {
    public static final Object LOCK = new Object();
    public static volatile String HOST = "10.0.2.2"; // emulator host alias; real devices set meta sink_host
    public static volatile int PORT = 8787;
    private static final String SEQ_PH = "SEQ_____________"; // 16 chars

    public static final class Item {
        public final String tag, kind, srcs, payload, labels; // labels may be null (variant does not persist them)
        public Item(String tag, String kind, String srcs, String payload, String labels) {
            this.tag = tag; this.kind = kind; this.srcs = srcs; this.payload = payload; this.labels = labels;
        }
    }
    public static final class Result {
        public final List<String> sent = new ArrayList<>(), blocked = new ArrayList<>();
        public int unknown = 0;
    }

    static String body(Context c, Model.Tenant t, String purpose, String job, String sid, int attempt, String path,
                       List<Item> items) {
        try {
            JSONObject o = new JSONObject();
            o.put("pkg", c.getPackageName()); o.put("variant", Model.variant(c).name);
            o.put("trial", Policy.trial(c)); o.put("tenant", t.id); o.put("purpose", purpose);
            o.put("job", job); o.put("sid", sid); o.put("attempt", attempt); o.put("path", path);
            o.put("commit_seq", SEQ_PH);
            JSONArray a = new JSONArray();
            for (Item it : items) {
                JSONObject x = new JSONObject();
                x.put("tag", it.tag); x.put("kind", it.kind); x.put("srcs", it.srcs); x.put("payload", it.payload);
                a.put(x);
            }
            o.put("items", a);
            return o.toString();
        } catch (JSONException e) { throw new RuntimeException(e); }
    }

    static byte[] encode(Model.Tenant t, String s) {
        byte[] b = s.getBytes(StandardCharsets.UTF_8);
        if (!t.opaque) return b;
        byte[] k = "residue-key".getBytes(StandardCharsets.UTF_8);
        for (int i = 0; i < b.length; i++) b[i] ^= k[i % k.length];
        String enc = "{\"opaque\":\"" + Base64.encodeToString(b, Base64.NO_WRAP) + "\"}";
        return enc.getBytes(StandardCharsets.UTF_8);
    }

    /** Variant decision for one item; null = allow; "U" = unknown label */
    static boolean blockedItem(Context c, Model.Variant v, Model.Tenant t, String purpose, String declaredScope, Item it, Result r) {
        if (!v.lineage) return Policy.blockedConv(c, t, declaredScope, purpose);
        String labels = v.durable ? it.labels : Policy.MEM_LABELS.get(it.tag);
        if (labels == null || labels.isEmpty()) {
            r.unknown++;
            return v.matched; // historical volatile ablation fails open on unknown provenance
        }
        for (String l : labels.split(",")) if (Policy.blockedLabel(c, t, l, purpose, v.contractAware)) return true;
        return false;
    }

    public static Result submit(Context c, Model.Tenant t, String purpose, String declaredScope, String job,
                                List<Item> items, int attempt) throws IOException {
        Model.Variant v = Model.variant(c);
        if (v.chunk) return ChunkFence.submit(c, t, purpose, declaredScope, job, items, attempt);
        Db db = Db.get(c);
        Result r = new Result();
        String sid = UUID.randomUUID().toString().substring(0, 13);
        HttpURLConnection conn = null;
        try {
            List<Item> send = items;
            if (v.egressCheck && !v.serialize) {           // noser ablation: check, (optional delay), then commit
                send = filter(c, v, t, purpose, declaredScope, items, r);
                if (v.raceDelayMs > 0) sleep(v.raceDelayMs);
            }
            if (send.isEmpty()) { logBlock(db, t, job, sid, r); return r; }
            // prepare the connection outside the critical section (TCP connect may take a while)
            String tmpl = body(c, t, purpose, job, sid, attempt, "mediated", send);
            byte[] enc0 = encode(t, tmpl);
            conn = (HttpURLConnection) new URL("http://" + HOST + ":" + PORT + "/ingest/" + purpose).openConnection();
            conn.setConnectTimeout(2500); conn.setReadTimeout(15000);
            conn.setDoOutput(true); conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("X-App", c.getPackageName()); conn.setRequestProperty("X-Trial", Policy.trial(c));
            conn.setFixedLengthStreamingMode(enc0.length);
            conn.connect();
            if (v.egressCheck && v.serialize) {
                synchronized (LOCK) {
                    send = filter(c, v, t, purpose, declaredScope, items, r);
                    if (send.size() != items.size()) { // re-encode with the reduced set (new length => new conn)
                        conn.disconnect(); conn = null;
                    } else {
                        commitAndWrite(c, db, t, job, sid, tmpl, conn, send, r);
                    }
                }
                if (conn == null) {
                    if (send.isEmpty()) { logBlock(db, t, job, sid, r); return r; }
                    return submitFiltered(c, t, purpose, declaredScope, job, send, attempt, r);
                }
            } else {
                commitAndWrite(c, db, t, job, sid, tmpl, conn, send, r);
            }
            int code = conn.getResponseCode();
            drain(conn);
            if (code != 200) throw new IOException("http " + code);
            for (Item it : send) r.sent.add(it.tag);
            return r;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /** Path taken when the fence dropped some items of a batch: resubmit only the survivors, still fenced. */
    static Result submitFiltered(Context c, Model.Tenant t, String purpose, String declaredScope, String job, List<Item> send, int attempt,
                                 Result r) throws IOException {
        Db db = Db.get(c);
        Model.Variant v = Model.variant(c);
        String sid = UUID.randomUUID().toString().substring(0, 13);
        String tmpl = body(c, t, purpose, job, sid, attempt, "mediated", send);
        byte[] enc0 = encode(t, tmpl);
        HttpURLConnection conn = (HttpURLConnection) new URL("http://" + HOST + ":" + PORT + "/ingest/" + purpose).openConnection();
        try {
            conn.setConnectTimeout(2500); conn.setReadTimeout(15000);
            conn.setDoOutput(true); conn.setRequestMethod("POST");
            conn.setRequestProperty("X-App", c.getPackageName()); conn.setRequestProperty("X-Trial", Policy.trial(c));
            conn.setFixedLengthStreamingMode(enc0.length);
            conn.connect();
            List<Item> again;
            synchronized (LOCK) {
                Result tmp = new Result();
                again = filter(c, v, t, purpose, declaredScope, send, tmp);
                if (again.size() != send.size()) { // a withdrawal raced in: drop everything newly invalid
                    r.blocked.addAll(tmp.blocked);
                    logBlock(db, t, job, sid, r);
                    return r;
                }
                commitAndWrite(c, db, t, job, sid, tmpl, conn, send, r);
            }
            int code = conn.getResponseCode();
            drain(conn);
            if (code != 200) throw new IOException("http " + code);
            for (Item it : send) r.sent.add(it.tag);
            return r;
        } finally { conn.disconnect(); }
    }

    static List<Item> filter(Context c, Model.Variant v, Model.Tenant t, String purpose, String declaredScope,
                             List<Item> items, Result r) {
        List<Item> out = new ArrayList<>();
        for (Item it : items) {
            if (blockedItem(c, v, t, purpose, declaredScope, it, r)) r.blocked.add(it.tag); else out.add(it);
        }
        return out;
    }

    static void logBlock(Db db, Model.Tenant t, String job, String sid, Result r) {
        db.event(t.id, "BLOCK", "job=" + job + ";sid=" + sid + ";n=" + r.blocked.size() + ";unknown=" + r.unknown);
    }

    static void commitAndWrite(Context c, Db db, Model.Tenant t, String job, String sid, String tmpl,
                               HttpURLConnection conn, List<Item> send, Result r) throws IOException {
        long seq = db.event(t.id, "COMMIT", "job=" + job + ";sid=" + sid + ";n=" + send.size() + ";unknown=" + r.unknown);
        String b = tmpl.replace(SEQ_PH, String.format(Locale.US, "%016d", seq));
        byte[] enc = encode(t, b);
        OutputStream os = conn.getOutputStream();
        os.write(enc);
        os.flush();
    }

    static void drain(HttpURLConnection conn) {
        try { InputStream is = conn.getInputStream(); byte[] buf = new byte[512]; while (is.read(buf) > 0) { } is.close(); }
        catch (IOException ignored) { }
    }

    /** Unmediated path: raw socket, bypasses the wrapper (stands in for JNI/custom network stacks). */
    public static void rawSend(Context c, Model.Tenant t, String purpose, String job, List<Item> items, int attempt) throws IOException {
        Db db = Db.get(c);
        String sid = UUID.randomUUID().toString().substring(0, 13);
        long seq = db.event(t.id, "UNMEDIATED_COMMIT", "job=" + job + ";sid=" + sid + ";n=" + items.size());
        String b = body(c, t, purpose, job, sid, attempt, "unmediated", items).replace(SEQ_PH, "unmediated______");
        byte[] bb = b.getBytes(StandardCharsets.UTF_8);
        Socket s = new Socket();
        try {
            s.connect(new java.net.InetSocketAddress(HOST, PORT), 2500);
            s.setSoTimeout(15000);
            OutputStream os = s.getOutputStream();
            String h = "POST /ingest/" + purpose + " HTTP/1.1\r\nHost: " + HOST + "\r\nContent-Type: application/json\r\nX-App: " + c.getPackageName() + "\r\nX-Trial: " + Policy.trial(c) + "\r\n"
                    + "Content-Length: " + bb.length + "\r\nConnection: close\r\n\r\n";
            os.write(h.getBytes(StandardCharsets.US_ASCII)); os.write(bb); os.flush();
            InputStream is = s.getInputStream();
            byte[] buf = new byte[64]; int n = is.read(buf);
            String line = n > 0 ? new String(buf, 0, n, StandardCharsets.US_ASCII) : "";
            if (!line.startsWith("HTTP/1.") || !line.contains(" 200")) throw new IOException("raw status " + line);
        } finally { s.close(); }
    }

    static void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException ignored) { } }
}
