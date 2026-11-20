#!/usr/bin/env python3
"""Live TLS 1.2 tests. Raw device and independently observed receiver logs are retained."""
from pathlib import Path
import argparse,subprocess,threading,socketserver,ssl,time,json,uuid,hashlib,os,contextlib
A=Path(__file__).resolve().parents[1];SDK=A.parents[1]/'shared-android/sdk';PKG='org.residuelab.tls'
p=argparse.ArgumentParser();p.add_argument('--n',type=int,default=20);p.add_argument('--start',type=int,default=0);p.add_argument('--deadline-ms',type=int);p.add_argument('--out',type=Path,required=True);p.add_argument('--serial',default='emulator-5644');p.add_argument('--no-root',action='store_true');p.add_argument('--host');p.add_argument('--cases',default='control,early,buffered-fence,buffered-early,stall-small,stall-large,concurrent,labels-complete,labels-incomplete,labels-missing,mixed');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
def adb(*args):
 r=subprocess.run([os.environ.get('ADB',str(SDK/'platform-tools/adb')),'-s',a.serial,*map(str,args)],capture_output=True,text=True,timeout=40)
 if r.returncode:raise RuntimeError(r.stderr)
 return r.stdout
def adb_try(*args):
 try:return adb(*args)
 except RuntimeError as e:return 'unavailable: '+str(e)[:200]
def bc(op,id,remote=False,**kw):
 if op=='send' and a.host:kw['host']=a.host
 cmd=['shell','am','broadcast','-n',PKG+'/org.residuelab.Revision'+('Remote' if remote else ''),'-a','rl.REVISION','--es','op',op,'--es','id',id]
 for k,v in kw.items():cmd+=['--ez' if isinstance(v,bool) else '--ei' if isinstance(v,int) else '--es',k,str(v).lower() if isinstance(v,bool) else str(v)]
 return adb(*cmd)
def events():
 rows=[]
 for l in adb('shell',f'run-as {PKG} cat files/revision.jsonl').splitlines():
  try:rows.append(json.loads(l))
  except ValueError:pass
 return rows
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(A/'followup/tls-cert/test-ca.pem',A/'followup/tls-cert/test-key.pem')
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
 def log(self,r):
  with self.guard:
   with (a.out/'receiver.jsonl').open('a')as f:f.write(json.dumps({'host_ns':time.monotonic_ns(),**r})+'\n')
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  id=None;total=0;expected=None;mode=self.server.mode
  try:
   self.request.settimeout(15)
   with (ctx.wrap_socket(self.request,server_side=True) if self.server.server_address[1]==8798 else contextlib.nullcontext(self.request)) as s:
    h=b''
    while not h.endswith(b'\r\n\r\n'):
     b=s.recv(1)
     if not b:raise EOFError('header')
     h+=b
    headers=dict(l.split(': ',1)for l in h.decode().split('\r\n')[1:]if ': 'in l);id=headers['X-Request-ID'];expected=int(headers['Content-Length'])
    self.server.log({'request':id,'event':'headers','expected':expected,'tls':s.version() if hasattr(s,'version') else 'plain'})
    if mode=='stall':time.sleep(12)
    while total<expected:
     b=s.recv(min(4096,expected-total))
     if not b:break
     total+=len(b)
    self.server.log({'request':id,'event':'body','received':total,'expected':expected,'complete':total==expected})
    if total==expected:s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
  except Exception as e:self.server.log({'request':id,'event':'error','error':repr(e),'received':total,'expected':expected})
sink=Server(('127.0.0.1',8798),Handler);sink.guard=threading.Lock();sink.mode='normal';threading.Thread(target=sink.serve_forever,daemon=True).start()
plain_sink=Server(('127.0.0.1',8799),Handler);plain_sink.guard=threading.Lock();plain_sink.mode='normal';threading.Thread(target=plain_sink.serve_forever,daemon=True).start()
(a.no_root or adb('root'));adb('wait-for-device');adb('install','-r',A/'fixture/build/tls-apk/rl-tls.apk');bc('init','setup')
adb('push',A/'followup/tls-cert/test-ca.pem','/data/local/tmp/p04-test-ca.pem');adb('shell',f'run-as {PKG} tee files/test-ca.pem < /data/local/tmp/p04-test-ca.pem > /dev/null')
(a.out/'environment.json').write_text(json.dumps({'fingerprint':adb('shell','getprop','ro.build.fingerprint').strip(),'serial':a.serial,'apk_sha256':hashlib.sha256((A/'fixture/build/tls-apk/rl-tls.apk').read_bytes()).hexdigest(),'started':time.time(),'host_load':os.getloadavg()},indent=2)+'\n')
for block in range(a.start,a.start+a.n):
 for case in a.cases.split(','):
  id='tls-'+case+'-'+str(block)+'-'+uuid.uuid4().hex[:6];r={'trial':id,'case':case,'block':block,'host_load':os.getloadavg(),'start':time.time()};sink.mode='stall' if case.startswith('stall')else 'normal'
  try:
   adb('shell',f'am force-stop {PKG}');adb('shell',f'run-as {PKG} rm -f files/revision.jsonl files/release');bc('init',id)
   label='analytics:0';size=1048576;fault='none';mode='early'if case in ['early','buffered-early','http-early']else'fence'
   if case.startswith('buffered'):fault='buffered';size=16384
   if case.startswith('labels')or case=='mixed':
    bc('labelsetup',id);size=1024
    label={'labels-complete':'analytics:0,diagnostics:0','labels-incomplete':'diagnostics:0','labels-missing':'?','mixed':'analytics:0,diagnostics:0'}[case]
   if case.startswith('stall'):size=8*1048576
   dl={'deadline_ms':a.deadline_ms} if a.deadline_ms else {};r['command']=bc('send',id,**dl,tls=not case.startswith('http'),labeltest=case.startswith('labels')or case=='mixed',mode=mode,fault=fault,size=size,port=8799 if case.startswith('http') else 8798,sndbuf=4096 if case=='stall-small' else 262144 if case=='stall-large' else 16384,label=label)
   ids=[id]
   if case in ['concurrent','http-concurrent']:ids.append(id+'-other');bc('send',ids[-1],remote=True,**dl,tls=not case.startswith('http'),mode=mode,fault='none',size=size,port=8799 if case.startswith('http') else 8798,label=label)
   if case.startswith('buffered')or case.startswith('stall'):
    target='TLS_BUFFERED'if case.startswith('buffered')else'BYTES_ACCEPTED';end=time.monotonic()+5
    while time.monotonic()<end:
     ev=events()
     if any(e['kind']==target for e in ev):break
     time.sleep(.02)
    r['barrier_seen']=any(e['kind']==target for e in ev)
    r['withdraw']=bc('withdraw',id,remote=True)
    r['tcp_after_withdraw']=adb_try('shell','cat /proc/net/tcp /proc/net/tcp6')
    if case.startswith('buffered'):adb('shell',f'run-as {PKG} touch files/release')
   end=time.monotonic()+max(13,(a.deadline_ms or 0)/1000+5)
   while time.monotonic()<end:
    ev=events()
    if all(any(e['trial']==x and e['kind']in['SEND_OK','SEND_ERROR','EARLY_BLOCK']for e in ev)for x in ids):break
    time.sleep(.05)
   r['events']=ev;r['completed_ids']=[x for x in ids if any(e['trial']==x and e['kind']in['SEND_OK','SEND_ERROR','EARLY_BLOCK']for e in ev)]
  except Exception as e:r['harness_error']=repr(e)
  r['finished']=time.time()
  with (a.out/'trials.jsonl').open('a')as f:f.write(json.dumps(r)+'\n')
  print(case,block,r.get('harness_error'),[(e['kind'],e['detail'][:90])for e in r.get('events',[])if e['kind']in['SEND_OK','SEND_ERROR','EARLY_BLOCK']],flush=True)
time.sleep(13 if 'stall' in a.cases else 1);sink.shutdown();plain_sink.shutdown()
