package org.residuelab;

import android.content.Context;
import android.content.Intent;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import org.residuelab.transport.HttpTransport;

/**
 * Group-3 harness and comparator helpers (g3race-card.md, g3cost-card.md), not part of ResidueDroid and not counted by
 * impLoc (kept in src-cmp). Revision.java only calls these from appended call sites.
 *  - hook(): per transport event; logs the request socket's local port after the TLS handshake (capture matching), marks
 *    the close2 token handed off at REQUEST_HANDED_OFF, and in fence-abort sets SO_LINGER 0 at the fence's BLOCK so the
 *    transport's close sends RST and discards unsent send-buffer data.
 *  - marker(): after WITHDRAW_ACK, one TCP connection to a host marker port; its SYN marks the ack in an independent
 *    packet capture (the guest shaper sends this port through an unshaped band).
 *  - platform(): the platform client (HttpsURLConnection, fixed-length streaming), no per-write check; cost comparator.
 */
final class G3 {
    private G3() { }

    static void hook(Context c, String id, String mode, CancelPath.Token tok, String kind) throws Exception {
        if (tok == null) return;
        if (kind.equals("TLS_HANDSHAKE")) Revision.event(c, id, "SOCKET_LOCAL", "local_port=" + tok.localPort());
        else if (kind.equals("REQUEST_HANDED_OFF")) tok.handed();
        else if (kind.equals("BLOCK") && "fence-abort".equals(mode)) Revision.event(c, id, "ABORT_ARMED", "linger0=" + tok.linger0());
    }

    static void marker(Context c, String id, Intent i) throws Exception {
        int port = i.getIntExtra("marker", 0);
        if (port <= 0) return;
        String host = i.hasExtra("marker_host") ? i.getStringExtra("marker_host") : "10.0.2.2";
        String res;
        try (Socket s = new Socket()) {
            s.setTcpNoDelay(true); s.connect(new InetSocketAddress(host, port), 3000);
            res = "local_port=" + s.getLocalPort();
            OutputStream o = s.getOutputStream(); o.write((id + "\n").getBytes(StandardCharsets.US_ASCII)); o.flush();
        } catch (Exception e) { res = "error=" + e; }
        Revision.event(c, id, "MARKER_SENT", "port=" + port + ";" + res);
    }

    static void platform(javax.net.ssl.SSLContext ctx, String host, int port, byte[] body, HttpTransport.Events ev,
                         String id, int timeoutMs) throws Exception {
        String prefix = "request=" + id + ";transport=platform;";
        javax.net.ssl.HttpsURLConnection h = (javax.net.ssl.HttpsURLConnection)
                new java.net.URL("https://" + host + ":" + port + "/ingest/analytics").openConnection();
        try {
            h.setSSLSocketFactory(ctx.getSocketFactory()); h.setConnectTimeout(timeoutMs); h.setReadTimeout(timeoutMs);
            h.setUseCaches(false); h.setDoOutput(true); h.setRequestMethod("POST"); h.setFixedLengthStreamingMode(body.length);
            h.setRequestProperty("X-Request-ID", id); h.setRequestProperty("Connection", "close");
            ev.emit("AUTHORIZATION_LOGGED", prefix + "plain_bytes=" + body.length);
            try (OutputStream o = h.getOutputStream()) { o.write(body); }
            ev.emit("REQUEST_HANDED_OFF", prefix + "plain_bytes=" + body.length);
            int code = h.getResponseCode(); ev.emit("RESPONSE_RECEIVED", prefix + "status=" + code);
            if (code != 200) throw new java.io.IOException("status " + code);
        } finally { h.disconnect(); }
    }
}
