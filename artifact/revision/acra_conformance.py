#!/usr/bin/env python3
"""Direct adapter/store conformance, separate from end-to-end SDK lifecycle trials."""
import argparse,json,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from socket_suite import Device,ART,ADB
p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(ART/'revision/freeze.py'),str(a.out/'frozen-run')],check=True)
d=Device(a.serial,a.out);pkg='org.residuelab.acrafence'
sink=subprocess.Popen([sys.executable,str(ART/'harness/sink.py'),'--port','8789','--out',str(a.out/'sink'),'--delay-ms','0'],stdout=open(a.out/'sink.log','w'),stderr=subprocess.STDOUT)
def bc(action,*extra):return d.adb('shell','am','broadcast','-n',pkg+'/org.residuelab.acra.Cmd','-a',action,*extra)
def reset():
 d.sh(f'pm clear {pkg}');d.sh(f'am start -W -n {pkg}/org.residuelab.acra.Main');time.sleep(.3)
def got(tag):
 p=a.out/'sink/ingest.jsonl'
 return p.exists() and any((json.loads(l).get('body',{}).get('CUSTOM_DATA') or {}).get('rd_tag')==tag for l in p.read_text().splitlines())
rows=[];trace=[]
try:
 d.adb('install','-r','-g',str(ART/'acra/build/apk/acrafence.apk'),timeout=120);time.sleep(.5)
 for name,label,operations,expected in [
  ('valid','crash:0',[],True),('missing','missing',[],False),('malformed','crash:oops',[],False),('future','crash:9',[],False),
  ('withdrawn','crash:0',['disable'],False),('old_after_regrant','crash:0',['disable','enable'],False),('new_after_regrant','crash:1',['disable','enable'],True),
  ('missing_store','crash:0',['missing_store'],False),('corrupt_store','crash:0',['corrupt_store'],False),
  ('legacy_invalid','crash:0',['legacy_invalid'],False),('legacy_withdrawn','crash:0',['legacy_withdrawn'],False),('legacy_allowed','crash:0',['legacy_allowed'],True),('invalid_migration_regrant','crash:0',['legacy_invalid','enable'],False),('missing_store_regrant','crash:0',['missing_store','enable'],False)]:
  reset();actions=[]
  for op in operations:
   if op in ['disable','enable']:actions.append(bc('rl.'+op.upper()))
   elif op=='missing_store':actions.append(d.sh(f'run-as {pkg} rm files/rd_policy.db'))
   elif op=='corrupt_store':actions.append(d.sh(f'run-as {pkg} sh -c "echo broken > files/rd_policy.db"'))
   elif op.startswith('legacy_'):
    d.sh(f'am force-stop {pkg}');d.sh(f'run-as {pkg} rm -f files/rd_policy.db files/rd_initialized')
    value={'legacy_invalid':'broken','legacy_withdrawn':'1 0','legacy_allowed':'0 1'}[op]
    d.sh(f'run-as {pkg} sh -c "echo {value} > files/rd_epoch"');d.sh(f'am start -W -n {pkg}/org.residuelab.acra.Main')
  tag='RD-conformance-'+name
  result=bc('rl.TEST_SEND','--es','label',label,'--es','tag',tag);time.sleep(.15)
  actual=got(tag);log=d.sh(f'run-as {pkg} cat files/rd_events.log');returned='sender returned' in result;denied=tag in log and ('BLOCK ' in log or 'REPORT_RETIRED policy_denied' in log)
  row=dict(case=name,label=label,operations=operations,expected_delivery=expected,delivered=actual,pass_=actual==expected and returned and (expected or denied),explicit_denial=denied,sender_returned=returned,actions=actions,result=result,log=log)
  rows.append(row);print(name,actual,row['pass_'],flush=True)
 # Preserve the settings contract as actual on-device UI hierarchy and pixels.
 reset();d.adb('shell','uiautomator','dump','/sdcard/p04-settings.xml');d.adb('pull','/sdcard/p04-settings.xml',str(a.out/'settings.xml'))
 screenshot=subprocess.run([str(ADB),'-s',a.serial,'exec-out','screencap','-p'],capture_output=True,check=True).stdout;(a.out/'settings.png').write_bytes(screenshot)
 import xml.etree.ElementTree as ET,re
 trace=[]
 for text,expected in [('Disable and withdraw queued reports','Withdrawal acknowledged'),('Enable new reports','Enabled; old reports remain invalid')]:
  xml=(a.out/'settings.xml').read_text();node=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')==text)
  x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']));d.adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(.5)
  d.adb('shell','uiautomator','dump','/sdcard/p04-settings.xml');target=a.out/('settings-disabled.xml' if text.startswith('Disable') else 'settings-enabled.xml');d.adb('pull','/sdcard/p04-settings.xml',str(target))
  trace.append(dict(tap=text,expected=expected,observed=expected in target.read_text(),events=d.sh(f'run-as {pkg} cat files/rd_events.log')))
 (a.out/'settings-contract-trace.json').write_text(json.dumps(trace,indent=2)+'\n')

finally:
 (a.out/'conformance.json').write_text(json.dumps(rows,indent=2)+'\n');sink.terminate();sink.wait(timeout=10)

if not all(r["pass_"] for r in rows) or not all(r["observed"] for r in trace):raise SystemExit("conformance or settings trace failed")
