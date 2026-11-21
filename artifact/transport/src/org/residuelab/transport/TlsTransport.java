package org.residuelab.transport;

import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.*;

/** Single-request HTTPS/1.1 over TLS 1.2. No redirects, pooling, early data or renegotiation.
 * Every application-record ciphertext write rechecks the conservative request label union.
 * wrap() is buffering, not socket acceptance; accepted ciphertext cannot be recalled.
 */
public final class TlsTransport {
    private static final ByteBuffer EMPTY=ByteBuffer.allocate(0);
    static void ready(Selector s,SelectionKey key,int op,long end)throws IOException {
        long left=end-System.nanoTime(); if(left<=0)throw new SocketTimeoutException("TLS deadline");
        key.interestOps(op);s.select(Math.max(1,Math.min(25,left/1000000)));s.selectedKeys().clear();
    }
    static void tasks(SSLEngine e){Runnable r;while((r=e.getDelegatedTask())!=null)r.run();}
    public static void post(SSLContext ctx,String host,int port,String path,byte[] body,File lock,
            HttpTransport.Policy policy,boolean fenced,HttpTransport.Events events,String request,
            int sendBuffer,int timeoutMillis)throws Exception {
        post(ctx,host,port,path,body,lock,policy,fenced,events,request,sendBuffer,timeoutMillis,null);
    }
    /** As above; onOpen (may be null) receives the channel right after it is opened, before connect. Used only by the
     * group-2 comparator (an early check plus a cancellation path that closes the socket); ResidueDroid does not use it. */
    public static void post(SSLContext ctx,String host,int port,String path,byte[] body,File lock,
            HttpTransport.Policy policy,boolean fenced,HttpTransport.Events events,String request,
            int sendBuffer,int timeoutMillis,java.util.function.Consumer<SocketChannel> onOpen)throws Exception {
        if(!path.matches("/[A-Za-z0-9/_-]*")||!request.matches("[A-Za-z0-9_-]+"))throw new IOException("invalid request");
        long deadline=System.nanoTime()+timeoutMillis*1000000L;
        String prefix="request="+request+";transport=tls12;";
        SSLEngine engine=ctx.createSSLEngine(host,port);engine.setUseClientMode(true);
        engine.setEnabledProtocols(new String[]{"TLSv1.2"});
        SSLParameters params=engine.getSSLParameters();params.setEndpointIdentificationAlgorithm("HTTPS");engine.setSSLParameters(params);
        int packet=engine.getSession().getPacketBufferSize(),app=engine.getSession().getApplicationBufferSize();
        ByteBuffer incoming=ByteBuffer.allocate(packet*2),outgoing=ByteBuffer.allocate(packet*2),plain=ByteBuffer.allocate(app*2);
        try(SocketChannel ch=SocketChannel.open();Selector selector=Selector.open()) {
            if(onOpen!=null)onOpen.accept(ch);
            ch.configureBlocking(false);ch.socket().setSendBufferSize(sendBuffer);
            events.emit("SOCKET_CONFIG",prefix+"requested_sndbuf="+sendBuffer+";actual_sndbuf="+ch.socket().getSendBufferSize());
            SelectionKey key=ch.register(selector,SelectionKey.OP_CONNECT);ch.connect(new InetSocketAddress(host,port));
            while(!ch.finishConnect())ready(selector,key,SelectionKey.OP_CONNECT,deadline);
            engine.beginHandshake();
            while(engine.getHandshakeStatus()!=SSLEngineResult.HandshakeStatus.NOT_HANDSHAKING) {
                if(System.nanoTime()>=deadline)throw new SocketTimeoutException("handshake deadline");
                SSLEngineResult.HandshakeStatus hs=engine.getHandshakeStatus();
                if(hs==SSLEngineResult.HandshakeStatus.NEED_TASK){tasks(engine);continue;}
                if(hs==SSLEngineResult.HandshakeStatus.NEED_WRAP){
                    outgoing.clear();SSLEngineResult r=engine.wrap(EMPTY,outgoing);
                    if(r.getStatus()!=SSLEngineResult.Status.OK)throw new SSLException("handshake wrap "+r);
                    outgoing.flip();while(outgoing.hasRemaining()){ready(selector,key,SelectionKey.OP_WRITE,deadline);ch.write(outgoing);}continue;
                }
                if(hs==SSLEngineResult.HandshakeStatus.NEED_UNWRAP){
                    incoming.flip();plain.clear();SSLEngineResult r=engine.unwrap(incoming,plain);incoming.compact();
                    if(r.getStatus()==SSLEngineResult.Status.BUFFER_UNDERFLOW){ready(selector,key,SelectionKey.OP_READ,deadline);if(ch.read(incoming)<0)throw new EOFException("handshake");}
                    else if(r.getStatus()!=SSLEngineResult.Status.OK)throw new SSLException("handshake unwrap "+r);
                    continue;
                }
                throw new SSLException("unexpected handshake state "+hs);
            }
            events.emit("TLS_HANDSHAKE",prefix+"protocol="+engine.getSession().getProtocol()+";cipher="+engine.getSession().getCipherSuite());
            byte[] header=("POST "+path+" HTTP/1.1\r\nHost: "+host+":"+port+"\r\nX-Request-ID: "+request+"\r\nContent-Length: "+body.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII);
            ByteBuffer data=ByteBuffer.allocate(header.length+body.length);data.put(header).put(body).flip();
            events.emit("AUTHORIZATION_LOGGED",prefix+"plain_bytes="+data.remaining());
            long accepted=0;int record=0;
            while(data.hasRemaining()) {
                int old=data.limit();data.limit(Math.min(old,data.position()+4096));outgoing.clear();
                SSLEngineResult r;try{r=engine.wrap(data,outgoing);}finally{data.limit(old);}
                if(r.getStatus()!=SSLEngineResult.Status.OK||r.bytesConsumed()==0||r.getHandshakeStatus()!=SSLEngineResult.HandshakeStatus.NOT_HANDSHAKING)throw new SSLException("application wrap "+r);
                outgoing.flip();final int recordId=record++;
                events.emit("TLS_BUFFERED",prefix+"record="+recordId+";plain_consumed="+r.bytesConsumed()+";cipher_produced="+r.bytesProduced());
                while(outgoing.hasRemaining()) {
                    ready(selector,key,SelectionKey.OP_WRITE,deadline);final int offset=outgoing.position();
                    Coordinator.Action<Integer> write=()->{
                        if(System.nanoTime()>=deadline)throw new SocketTimeoutException("write deadline");
                        if(fenced&&!policy.permitted()){events.emit("BLOCK",prefix+"record="+recordId+";pending_cipher="+outgoing.remaining());throw new HttpTransport.Denied();}
                        int limit=outgoing.limit();outgoing.limit(Math.min(limit,offset+4096));
                        String detail=prefix+"record="+recordId+";offset="+offset;
                        events.emit("WRITE_ATTEMPT",detail+";requested="+outgoing.remaining());
                        int n;try{n=ch.write(outgoing);}finally{outgoing.limit(limit);}
                        events.emit("WRITE_RETURN_BOUNDARY",detail);
                        events.emit("BYTES_ACCEPTED",detail+";n="+n);return n;
                    };
                    accepted+=fenced?Coordinator.call(lock,deadline,write):write.run();
                }
            }
            events.emit("REQUEST_HANDED_OFF",prefix+"cipher_bytes="+accepted+";plain_bytes="+(header.length+body.length));
            StringBuilder response=new StringBuilder();
            while(response.indexOf("\r\n")<0){
                incoming.flip();plain.clear();SSLEngineResult r=engine.unwrap(incoming,plain);incoming.compact();plain.flip();response.append(StandardCharsets.US_ASCII.decode(plain));
                if(response.length()>4096)throw new IOException("response limit");
                if(r.getHandshakeStatus()==SSLEngineResult.HandshakeStatus.NEED_TASK)tasks(engine);
                if(r.getStatus()==SSLEngineResult.Status.CLOSED&&response.indexOf("\r\n")<0)throw new EOFException("TLS response");
                if(r.getStatus()==SSLEngineResult.Status.BUFFER_UNDERFLOW||r.bytesConsumed()==0){ready(selector,key,SelectionKey.OP_READ,deadline);if(ch.read(incoming)<0)throw new EOFException("response");}
            }
            String status=response.substring(0,response.indexOf("\r\n"));events.emit("RESPONSE_RECEIVED",prefix+"status="+status);
            if(!status.matches("HTTP/1\\.[01] 200(?: .*)?"))throw new IOException(status);
        }catch(Exception e){events.emit("SEND_FAILED",prefix+"error="+e.getClass().getSimpleName());throw e;}
        finally{engine.closeOutbound();}
    }
}
