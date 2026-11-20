package org.residuelab.transport;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Audited plain HTTP/1.1 POST. No TLS, proxy, redirect, connection pool, or stream buffering.
 * Each positive SocketChannel.write return is an accepted prefix, NOT remote delivery.
 * One channel has one writer; a request's conservative source union is checked per chunk.
 */
public final class HttpTransport {
    public static final int CHUNK = 4096;
    public interface Policy { boolean permitted() throws Exception; }
    public interface Events { void emit(String kind, String detail) throws Exception; }
    public static final class Denied extends IOException { public Denied() { super("policy denied remaining bytes"); } }
    private static void ready(Selector s, SelectionKey key, int op, long deadline) throws IOException {
        long left = deadline - System.nanoTime();
        if (left <= 0) throw new java.net.SocketTimeoutException("HTTP operation deadline");
        key.interestOps(op); s.select(Math.max(1, Math.min(50, left / 1000000))); s.selectedKeys().clear();
    }
    public static void post(String host, int port, String path, byte[] body, File lock,
                            Policy policy, boolean fenced, Events events, String request, int attempt) throws Exception {
        postMode(host,port,path,body,lock,policy,fenced,false,events,request,attempt);
    }
    /** wholeWrite is a matched transport comparator: only its write phase holds the lock. */
    public static void postMode(String host,int port,String path,byte[] body,File lock,Policy policy,
                                boolean fenced,boolean wholeWrite,Events events,String request,int attempt)throws Exception {
        postMode(host,port,path,body,lock,policy,fenced,wholeWrite,events,request,attempt,CHUNK,5000);
    }
    /** B4/test 5: chunk size and operation deadline as parameters (defaults above: CHUNK, 5 s). */
    public static void postMode(String host,int port,String path,byte[] body,File lock,Policy policy,
                                boolean fenced,boolean wholeWrite,Events events,String request,int attempt,
                                int chunk,int deadlineMillis)throws Exception {
        if (!path.matches("/[A-Za-z0-9/_-]*")) throw new IOException("unsupported path");
        final long deadline = System.nanoTime() + deadlineMillis * 1_000_000L;
        String prefix = "v=2;request=" + request + ";attempt=" + attempt + ";";
        byte[] header = ("POST " + path + " HTTP/1.1\r\nHost: " + host + ":" + port
            + "\r\nContent-Type: application/json\r\nX-Request-ID: " + request
            + "\r\nContent-Length: " + body.length + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII);
        ByteBuffer wire = ByteBuffer.allocate(header.length + body.length); wire.put(header).put(body).flip();
        try (SocketChannel channel = SocketChannel.open(); Selector selector = Selector.open()) {
            channel.configureBlocking(false); channel.socket().setSendBufferSize(16384);
            SelectionKey key = channel.register(selector, SelectionKey.OP_CONNECT);
            channel.connect(new InetSocketAddress(host, port));
            while (!channel.finishConnect()) ready(selector, key, SelectionKey.OP_CONNECT, deadline);
            // Unfenced baselines log authorization here; it cannot be treated as byte handoff.
            events.emit("AUTHORIZATION_LOGGED", prefix + "fenced=" + fenced);
            Coordinator.Action<Void> writePhase = () -> {
                if(wholeWrite && !policy.permitted())throw new Denied();
            while (wire.hasRemaining()) {
                ready(selector, key, SelectionKey.OP_WRITE, deadline);
                final int offset = wire.position(), end = Math.min(wire.limit(), offset + chunk);
                Coordinator.Action<Integer> write = () -> {
                    if (System.nanoTime() >= deadline) throw new java.net.SocketTimeoutException("write deadline");
                    if (fenced && !wholeWrite && !policy.permitted()) { events.emit("BLOCK", prefix + "offset=" + offset); throw new Denied(); }
                    events.emit("WRITE_ATTEMPT", prefix + "offset=" + offset + ";requested=" + (end-offset));
                    int oldLimit = wire.limit(); wire.limit(end);
                    int n;
                    try { n = channel.write(wire); } finally { wire.limit(oldLimit); }
                    events.emit("WRITE_RETURN_BOUNDARY", prefix + "offset=" + offset);
                    // If death intervenes before this event, the attempted prefix is UNKNOWN, not zero.
                    events.emit("BYTES_ACCEPTED", prefix + "offset=" + offset + ";n=" + n);
                    return n;
                };
                if (fenced && !wholeWrite) Coordinator.call(lock, deadline, write); else write.run();
            }
                return null;
            };
            if(wholeWrite)Coordinator.call(lock,deadline,writePhase);else writePhase.run();
            events.emit("REQUEST_HANDED_OFF", prefix + "wire_bytes=" + wire.position());
            ByteBuffer buf = ByteBuffer.allocate(1024); StringBuilder response = new StringBuilder();
            while (response.indexOf("\r\n") < 0) {
                ready(selector, key, SelectionKey.OP_READ, deadline);
                int n = channel.read(buf);
                if (n < 0) throw new EOFException("no complete response status");
                buf.flip(); response.append(StandardCharsets.US_ASCII.decode(buf)); buf.clear();
                if (response.length() > 4096) throw new IOException("response status too long");
            }
            String status = response.substring(0, response.indexOf("\r\n"));
            events.emit("RESPONSE_RECEIVED", prefix + "status=" + status);
            if (!status.matches("HTTP/1\\.[01] 200(?: .*)?")) throw new IOException(status);
        } catch (Exception e) { events.emit("SEND_FAILED", prefix + "error=" + e.getClass().getSimpleName()); throw e; }
    }
}
