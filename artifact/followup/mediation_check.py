#!/usr/bin/env python3
"""DEX direct-call audit, not a complete-mediation proof. Unreachable library sites remain flags."""
from pathlib import Path
import sys,json,zipfile,re,hashlib
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'static'))
from dexscan import Dex,NET_EXACT
SINKS=NET_EXACT|{('Ljava/nio/channels/SocketChannel;',m)for m in ['write','connect']}|{('Ljava/net/HttpURLConnection;',m)for m in ['connect','getOutputStream']}|{('Ljavax/net/ssl/HttpsURLConnection;',m)for m in ['connect','getOutputStream']}
APPROVED={'Lorg/residuelab/transport/HttpTransport;','Lorg/residuelab/transport/TlsTransport;'}
rows=[]
for apk in [A/'acra/build/apk/acrafence.apk',A/'matomo/build/matomo.apk']:
 sites=[]
 with zipfile.ZipFile(apk)as z:
  for name in sorted(z.namelist()):
   if not re.fullmatch(r'classes\d*\.dex',name):continue
   d=Dex(z.read(name))
   for cls,_,_,methods in d.classes():
    for method,off in methods:
     for target in d.code_refs(off)[0]:
      if target in SINKS or (target[0]in['Lokhttp3/Call;','Lokhttp3/RealCall;']and target[1]in['execute','enqueue']):
       allowed=cls in APPROVED or cls.startswith('Lorg/residuelab/transport/HttpTransport$')or cls.startswith('Lorg/residuelab/transport/TlsTransport$')
       sites.append({'caller':cls+'->'+method,'target':'->'.join(target),'status':'approved transport class'if allowed else'potential bypass; reachability/configuration review required'})
 rows.append({'apk':str(apk.relative_to(A)),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'sites':sites,'potential_bypass_sites':sum(x['status'].startswith('potential')for x in sites)})
out=A/'results/review-followup-20261115/mediation.json';out.write_text(json.dumps({'limitations':['direct DEX calls only','no native, reflection, dynamic loading or IPC proof','method overloads merged by inherited parser','SDK dead code remains flagged'],'apks':rows},indent=2)+'\n')
for r in rows:print(r['apk'],len(r['sites']),r['potential_bypass_sites'])
