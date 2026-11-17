import org.residuelab.transport.*;
import java.net.*;import java.io.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;
public class TestTransport {
 static void require(boolean p,String msg){if(!p)throw new AssertionError(msg);}
 static void responseOutsideLock(boolean whole)throws Exception {
  File lock=File.createTempFile("rd-lock-", ".lock");lock.deleteOnExit();CountDownLatch handoff=new CountDownLatch(1),response=new CountDownLatch(1);
  AtomicReference<Throwable> fail=new AtomicReference<>();AtomicInteger accepted=new AtomicInteger();
  try(ServerSocket server=new ServerSocket(0)) {
   Thread receiver=new Thread(()->{try(Socket s=server.accept()){
    InputStream in=s.getInputStream();StringBuilder h=new StringBuilder();int b;while((b=in.read())>=0){h.append((char)b);if(h.toString().endsWith("\r\n\r\n"))break;}
    int length=Integer.parseInt(h.toString().split("Content-Length: ")[1].split("\r\n")[0]);int total=0;byte[] buf=new byte[8192];while(total<length){int n=in.read(buf,0,Math.min(buf.length,length-total));if(n<0)break;total+=n;}
    require(total==length,"receiver incomplete");response.await(2,TimeUnit.SECONDS);
    s.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n".getBytes());
   }catch(Throwable e){fail.set(e);}});receiver.start();
   Thread sender=new Thread(()->{try{HttpTransport.postMode("127.0.0.1",server.getLocalPort(),"/test",new byte[20000],lock,()->true,true,whole,(kind,detail)->{
    if(kind.equals("BYTES_ACCEPTED"))accepted.addAndGet(Integer.parseInt(detail.substring(detail.lastIndexOf("n=")+2)));
    if(kind.equals("REQUEST_HANDED_OFF"))handoff.countDown();
   },"test",1);}catch(Throwable e){fail.set(e);}});sender.start();
   require(handoff.await(3,TimeUnit.SECONDS),"handoff absent");
   long start=System.nanoTime();Coordinator.call(lock,start+300_000_000L,()->null);
   require(System.nanoTime()-start<300_000_000L,"response held policy lock");response.countDown();sender.join(3000);receiver.join(3000);
   require(!sender.isAlive()&&!receiver.isAlive(),"threads stuck");require(fail.get()==null,"failure: "+fail.get());require(accepted.get()>20000,"missing header/body count");
  }
 }
 public static void main(String[] args)throws Exception {responseOutsideLock(false);responseOutsideLock(true);System.out.println("PASS chunk and whole-write comparator release lock before response");}
}
