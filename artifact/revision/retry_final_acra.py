#!/usr/bin/env python3
import subprocess,sys,json,time
from pathlib import Path
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115'
sys.path.insert(0,str(ART/'revision'))
from socket_suite import Device
d=Device('emulator-5640',ROOT)
old=[]
for pkg in ['org.residuelab.acra','org.residuelab.acrafence']:
 path=d.adb('shell','pm','path',pkg).strip().removeprefix('package:')
 old.append(dict(package=pkg,old_sha256=d.adb('shell','sha256sum',path).split()[0] if path else None,uninstall=d.adb('uninstall',pkg)))
(ROOT/'acra-A-old-signature-removal.json').write_text(json.dumps(old,indent=2)+'\n')
for name,args in [('acra-conformance-final',['revision/acra_conformance.py','--serial','emulator-5640']),('acra-final-A',['revision/acra_case_v4.py','--serial','emulator-5640','--avd','P04AvdA','--trials','1','--reboot-trials','0'])]:
 out=ROOT/name;out.mkdir(exist_ok=True)
 with (out/'final-stage.log').open('a') as log:code=subprocess.call([sys.executable,'-u',str(ART/args[0]),*args[1:],'--out',str(out)],stdout=log,stderr=subprocess.STDOUT)
 with (ROOT/'final-A.jsonl').open('a') as f:f.write(json.dumps(dict(stage=name,exit=code,time=time.time(),recovery='removed old inherited test signing keys'))+'\n')
 if code:raise SystemExit(code)
installed=[]
for pkg in ['org.residuelab.acra','org.residuelab.acrafence']:
 path=d.adb('shell','pm','path',pkg).strip().removeprefix('package:');installed.append(dict(package=pkg,sha256=d.adb('shell','sha256sum',path).split()[0]))
(ROOT/'acra-final-installed-sha256.json').write_text(json.dumps(installed,indent=2)+'\n')
