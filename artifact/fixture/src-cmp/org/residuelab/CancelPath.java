package org.residuelab;

import android.content.*;
import java.nio.channels.SocketChannel;
import java.util.Set;
import java.util.concurrent.*;

/**
 * Group-2 comparator (g2close-card.md), not part of ResidueDroid: the layered early check plus a cancellation path that
 * closes the socket of every in-flight request when a withdrawal commits, before the withdrawal is acknowledged.
 * Built as the strongest form we could write without a per-write check:
 *  - a request registers a token BEFORE its early check, so a withdrawal either sees the token (and closes its socket,
 *    or makes the transport close it the moment it opens) or commits before the check (which then blocks);
 *  - the withdrawing process (:revision) asks the sending process synchronously (ordered broadcast, foreground queue)
 *    and acknowledges only after the reply or a 5 s timeout (logged).
 * Kept out of fixture/src so the implementation size (render.py impLoc) does not count comparator code.
 */
public final class CancelPath {
    public static final class Token implements java.util.function.Consumer<SocketChannel> {
        private boolean cancelled, handed; private SocketChannel ch;
        @Override public synchronized void accept(SocketChannel c) { ch = c; if (cancelled) close(); }   // TlsTransport: right after open
        synchronized boolean cancel() { cancelled = true; return close(); }
        /** Group 3 (g3race-card.md): REQUEST_HANDED_OFF seen; close2 leaves such a request alone. */
        synchronized void handed() { handed = true; }
        /** close2: cancel only a request not yet handed off. -1 = handed off (left alone), 1 = socket closed, 0 = no socket yet. */
        synchronized int cancelUnhanded() { if (handed) return -1; cancelled = true; return close() ? 1 : 0; }
        /** fence-abort: make the coming close abortive (SO_LINGER 0: RST, unsent send-buffer data discarded). */
        synchronized boolean linger0() {
            if (ch == null) return false;
            try { ch.socket().setSoLinger(true, 0); return true; } catch (Exception e) { return false; }
        }
        synchronized int localPort() { return ch == null ? -1 : ch.socket().getLocalPort(); }
        private boolean close() {
            if (ch == null) return false;
            try { ch.close(); } catch (Exception ignored) { }
            return true;
        }
    }

    private static final Set<Token> LIVE = ConcurrentHashMap.newKeySet();

    static Token register() { Token t = new Token(); LIVE.add(t); return t; }

    static void done(Token t) { if (t != null) LIVE.remove(t); }

    /** Sending process (op=cancel): cancel every live request; reports how many were live and how many had a socket. */
    static String cancelAll() {
        int live = 0, closed = 0;
        for (Token t : LIVE) { live++; if (t.cancel()) closed++; }
        return "live=" + live + ";closed=" + closed;
    }

    /** Group 3 close2: called in the sending process itself, right after the withdrawal is durable and before its ack. */
    static String cancelUnhanded() {
        int live = 0, closed = 0, nosocket = 0, handed = 0;
        for (Token t : LIVE) { live++; int r = t.cancelUnhanded(); if (r > 0) closed++; else if (r == 0) nosocket++; else handed++; }
        return "live=" + live + ";closed=" + closed + ";nosocket=" + nosocket + ";handed=" + handed;
    }

    /** Withdrawing process, after the withdrawal is durable and before its ack. Returns the reply, or "timeout". */
    static String request(Context c, String id, long timeoutMs) throws InterruptedException {
        CountDownLatch done = new CountDownLatch(1); String[] res = {"timeout"};
        Intent i = new Intent("rl.REVISION").setComponent(new ComponentName(c, Revision.class))
                .putExtra("op", "cancel").putExtra("id", id).addFlags(Intent.FLAG_RECEIVER_FOREGROUND);
        c.sendOrderedBroadcast(i, null, new BroadcastReceiver() {
            @Override public void onReceive(Context x, Intent r) { res[0] = String.valueOf(getResultData()); done.countDown(); }
        }, null, 0, null, null);
        done.await(timeoutMs, TimeUnit.MILLISECONDS);
        return res[0];
    }
}
