#!/usr/bin/env python3
"""Revision-only socket acceptance/crash/backpressure tests; every attempt is retained.
The receiver logs raw partial prefixes independently of device authorization events.
"""
import argparse,concurrent.futures,json,os,socket,socketserver,subprocess,threading,time,uuid,sys
from pathlib import Path
ART=Path(__file__).resolve().parents[1]
ADB=Path(os.environ.get('ANDROID_HOME',str(ART.parents[1]/'shared-android/sdk')))/'platform-tools/adb'
PKG='org.residuelab.mfence'
class Sink(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
 def __init__(self,port,out):
  self.out=out;self.mode='normal';self.lock=threading.Lock();super().__init__(('127.0.0.1',port),Handler)
 def log(self,obj):
  with self.lock:
   with (self.out/'receiver.jsonl').open('a') as f:f.write(json.dumps({'host_ns':time.monotonic_ns(),**obj})+'\n')
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  mode=self.server.mode;conn=str(uuid.uuid4());buf=b'';req=None;total=0;expected=None
  self.request.settimeout(7)
  # Read headers without consuming body so stalls really apply before body consumption.
  try:
   while b'\r\n\r\n' not in buf and len(buf)<8192:
    b=self.request.recv(1)
    if not b:break
    buf+=b
   head=buf.decode('ascii',errors='replace')
   for line in head.split('\r\n'):
    if line.lower().startswith('x-request-id:'):req=line.split(':',1)[1].strip()
    if line.lower().startswith('content-length:'):expected=int(line.split(':',1)[1])
   self.server.log({'event':'headers','connection':conn,'request':req,'mode':mode,'expected':expected})
   if mode=='stalled':time.sleep(6)
   receive_deadline=time.monotonic()+7
   while expected is not None and total<expected and time.monotonic()<receive_deadline:
    b=self.request.recv(min(1024 if mode=='slow' else 65536,expected-total))
    if not b:break
    total+=len(b)
    self.server.log({'event':'prefix','connection':conn,'request':req,'received_body':total})
    if mode=='slow':time.sleep(1)
   if expected is not None and total==expected:
    self.server.log({'event':'complete_request','request':req,'received_body':total})
    if mode=='response':time.sleep(6)
    self.request.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
  except Exception as e:self.server.log({'event':'receiver_error','request':req,'error':repr(e)})
  finally:self.server.log({'event':'connection_end','request':req,'received_body':total,'expected':expected})
class Device:
 def __init__(self,serial,out):self.serial=serial;self.out=out
 def adb(self,*args,timeout=30):
  r=subprocess.run([str(ADB),'-s',self.serial,*args],capture_output=True,text=True,timeout=timeout)
  if r.returncode:raise RuntimeError(r.stderr)
  return r.stdout
 def sh(self,s):return self.adb('shell',s)
 def bc(self,op,id,remote=False,**kw):
  cmd=['shell','am','broadcast','-n',PKG+'/org.residuelab.Revision'+('Remote' if remote else ''),'-a','rl.REVISION','--es','op',op,'--es','id',id]
  for k,v in kw.items():cmd+=['--ei' if isinstance(v,int) else '--es',k,str(v)]
  return self.adb(*cmd)
 def events(self):
  raw=self.sh(f'run-as {PKG} cat files/revision.jsonl 2>/dev/null');rows=[]
  for line in raw.splitlines():
   try:rows.append(json.loads(line))
   except Exception:pass
  return rows
 def wait(self,id,kind,timeout=5):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   if any(e['trial']==id and e['kind']==kind for e in self.events()):return True
   time.sleep(.05)
  return False
 def trial(self,sink,case,block):
  id=f'{self.serial}-{block}-{uuid.uuid4().hex[:10]}'
  r={'trial':id,'serial':self.serial,'block':block,**case,'started':time.time()};sink.mode=case.get('load','normal')
  try:
   r['boot_id']=self.sh('cat /proc/sys/kernel/random/boot_id').strip()
   self.sh(f'am force-stop {PKG}');self.sh(f'run-as {PKG} rm -f files/release files/revision.jsonl')
   r['init']=self.bc('init',id)
   with concurrent.futures.ThreadPoolExecutor() as pool:
    future=pool.submit(self.bc,'send',id,mode=case.get('mode','fence'),fault=case.get('fault','none'),size=case.get('size',16384),port=sink.server_address[1],label=case.get('label','analytics:0'))
    barrier=case.get('barrier','AUTHORIZATION_LOGGED')
    r['barrier_seen']=self.wait(id,barrier,5)
    if case.get('withdraw') and r['barrier_seen']:
     r['withdraw_call_host_start_ns']=time.monotonic_ns()
     r['withdraw']=self.bc('withdraw',id,remote=case.get('remote',False),tenant=case.get('tenant',1))
     r['withdraw_return_host_ns']=time.monotonic_ns()
     r['withdraw_command_ms']=(r['withdraw_return_host_ns']-r['withdraw_call_host_start_ns'])/1e6
    if case.get('fault')=='barrier':self.sh(f'run-as {PKG} touch files/release')
    try:r['send_command']=future.result(timeout=30)
    except Exception as e:r['send_command_error']=repr(e)
   end=time.monotonic()+7
   while time.monotonic()<end:
    ev=[e for e in self.events() if e['trial']==id]
    if any(e['kind'] in ['SEND_OK','SEND_ERROR','EARLY_BLOCK'] for e in ev) or case.get('group')=='crash':break
    time.sleep(.1)
   if case.get('retry'):
    r['retry']=self.bc('send',id+'-retry',mode='fence',size=16384,port=sink.server_address[1],attempt=2)
   if case.get('regrant'):
    self.bc('regrant',id);r['old_after_regrant']=self.bc('send',id+'-old',mode='fence',size=1024,port=sink.server_address[1],epoch=0)
    r['new_after_regrant']=self.bc('send',id+'-new',mode='fence',size=1024,port=sink.server_address[1],epoch=1)
    self.wait(id+'-new','SEND_OK',6)
   r['events']=[e for e in self.events() if e['trial'].startswith(id)]
  except Exception as e:r['harness_error']=repr(e)
  r['finished']=time.time()
  with (self.out/'trials.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
  print(id,case.get('group'),case.get('load'),case.get('fault'),r.get('harness_error',''),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--port',type=int,default=8794);p.add_argument('--out',type=Path,required=True);p.add_argument('--blocks',type=int,default=10);p.add_argument('--start',type=int,default=0);p.add_argument('--deadline',type=float,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 subprocess.run([sys.executable,str(ART/'revision/freeze.py'),str(a.out/f'frozen-start{a.start}')],check=True)
 sink=Sink(a.port,a.out);threading.Thread(target=sink.serve_forever,daemon=True).start();d=Device(a.serial,a.out)
 d.adb('install','-r','-g',str(ART/'fixture/build/socket-v3-apk/rl-mfence.apk'),timeout=120)
 packages=[line.removeprefix('package:').strip() for line in d.sh('pm list packages org.residuelab').splitlines() if line.startswith('package:org.residuelab.')]
 for package in packages:d.adb('shell','am','force-stop',package)
 d.adb('shell','pm','clear',PKG)
 (a.out/f'environment-start{a.start}.json').write_text(json.dumps({'serial':a.serial,'boot_id':d.sh('cat /proc/sys/kernel/random/boot_id').strip(),'fingerprint':d.sh('getprop ro.build.fingerprint').strip(),'stopped_fixture_packages':packages},indent=2)+'\n')
 cases=[]
 for mode in ['early','fence']:cases.append(dict(group='ordering',mode=mode,fault='barrier',withdraw=True,remote=True))
 for fault,barrier in [('afterlog','AUTHORIZATION_LOGGED'),('partial','BYTES_ACCEPTED'),('unlogged','WRITE_RETURN_BOUNDARY'),('response','REQUEST_HANDED_OFF')]:
  cases.append(dict(group='crash',fault=fault,barrier=barrier,withdraw=True,remote=True,retry=True,regrant=True))
 for label in ['missing','analytics:bad','analytics:9','other:0','analytics:0']:
  cases.append(dict(group='labels',label=label,barrier='EARLY_BLOCK' if label!='analytics:0' else 'AUTHORIZATION_LOGGED'))
 for load in ['normal','slow','stalled','response','long']:
  for remote in [False,True]:
   for tenant in [1,6]:
    for mode in ['whole','fence']:
     cases.append(dict(group='backpressure',load=load,remote=remote,tenant=tenant,mode=mode,withdraw=True,size=1024*1024 if load=='long' else (8*1024*1024 if load in ['slow','stalled'] else 16384)))
 (a.out/f'matrix-start{a.start}.json').write_text(json.dumps({'cases':cases,'blocks':a.blocks,'deadline':a.deadline},indent=2))
 for block in range(a.start,a.start+a.blocks):
  for case in cases:
   if time.time()>=a.deadline:sink.shutdown();return
   d.trial(sink,case,block)
 sink.shutdown()
if __name__=='__main__':main()
