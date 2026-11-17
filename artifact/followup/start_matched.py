from pathlib import Path
import os,subprocess,time,json
A=Path(__file__).resolve().parents[1];S=A.parents[1]/'shared-android';R=A/'results/review-followup-20261115'
env={**os.environ,'ANDROID_AVD_HOME':str(S/'avd'),'ANDROID_HOME':str(S/'sdk'),'ANDROID_SDK_ROOT':str(S/'sdk')}
jobs=[]
for name,port,sink in [('A',5640,8795),('B',5642,8796)]:
 out=R/('matched-'+name);out.mkdir(exist_ok=True)
 log=(out/'emulator.log').open('w')
 p=subprocess.Popen([str(S/'sdk/emulator/emulator'),'-avd','P04Avd'+name,'-port',str(port),'-read-only','-no-snapshot','-no-window','-no-audio','-gpu','host','-feature','-Vulkan','-memory','3072'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 jobs.append((name,port,sink,out,p.pid))
for name,port,sink,out,pid in jobs:
 adb=[str(S/'sdk/platform-tools/adb'),'-s',f'emulator-{port}']
 end=time.time()+240
 while time.time()<end:
  r=subprocess.run(adb+['shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=15)
  if r.stdout.strip()=='1':break
  time.sleep(2)
 else:raise RuntimeError('boot timeout '+name)
 subprocess.run(adb+['root'],capture_output=True);subprocess.run(adb+['wait-for-device'],timeout=60)
 log=(out/'campaign.log').open('w')
 cmd=['python3','-u',str(A/'followup/campaign.py'),'--serial',f'emulator-{port}','--avd','P04Avd'+name,'--port',str(sink),'--variants','menqueue,mstart,mlayer,mfence,mboth','--trials','20','--out',str(out),'--apkdir','fixture/build/revision-apk','--timeout','90','--seed','followup-20261115']
 p=subprocess.Popen(cmd,cwd=A,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (out/'launch.json').write_text(json.dumps({'emulator_pid':pid,'campaign_pid':p.pid,'command':cmd,'started':time.time(),'renderer':'host; Vulkan disabled','readonly':True},indent=2)+'\n')
 print(name,'campaign',p.pid,flush=True)
