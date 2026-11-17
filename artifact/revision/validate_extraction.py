#!/usr/bin/env python3
"""Validate a fresh extraction, then compare all deterministic derived outputs."""
import argparse, hashlib, json, os, subprocess, tempfile, time
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--skip-apk',action='store_true');ap.add_argument('--forbid',action='append',default=[]);a=ap.parse_args()
    root=a.root.resolve();art=root/'artifact';report=dict(started=time.time(),commands=[],numeric_outputs=0,differences=[],status='running')
    def run(args,env=None):
        print('RUN',args,flush=True);r=subprocess.run(args,cwd=root,env=env);report['commands'].append(dict(args=args,exit=r.returncode));r.check_returncode()
    derived=list((root/'manuscript/generated').glob('*.tex'))+[p for p in (art/'results').glob('*.csv') if p.name!='static_validation_judged.csv']
    derived += [art/'results'/x for x in ['summary_campaign.json','static_summary.json']]
    rev=art/'results/revision-20261115'
    derived += [rev/x for x in ['socket-outcomes.json','socket-summary.json','socket-summary-by-avd.json','matched-outcomes.json','matched-summary.json','matched-paired-contrasts.json','historical-cluster-bootstrap.json','evidence-audit.json']]
    before={str(p.relative_to(root)):sha(p) for p in derived if p.exists()}
    try:
        run(['python3','artifact/revision/verify_package.py',str(root),*[x for v in a.forbid for x in ['--forbid',v]]])
        run(['make','-C','artifact','all'])
        report['numeric_outputs']=len(before)
        report['differences']=[n for n,h in before.items() if sha(root/n)!=h]
        if report['differences']:raise RuntimeError('derived output mismatch')
        run(['python3','-m','unittest','discover','-s','artifact/revision','-p','test_*.py'])
        if not a.skip_apk:
            if not os.environ.get('JAVA_HOME') or not os.environ.get('ANDROID_HOME'):raise RuntimeError('set JAVA_HOME and ANDROID_HOME')
            env={**os.environ,'VARIANTS':'menqueue mstart mlayer mfence mboth','OUTDIR':'build/rebuilt-revision-apk'}
            run(['bash','artifact/fixture/build.sh'],env)
            for project in ['acra','matomo','workmanager']:run(['bash',f'artifact/{project}/build.sh'])
            with tempfile.TemporaryDirectory(prefix='rd-transport-check-') as td:
                sources=[str(p) for p in (art/'transport/src').rglob('*.java')]+[str(art/'transport/tests/TestTransport.java')]
                run([str(Path(os.environ['JAVA_HOME'])/'bin/javac'),'-d',td,*sources])
                run([str(Path(os.environ['JAVA_HOME'])/'bin/java'),'-cp',td,'TestTransport'])
        report['status']='passed'
    except Exception as e:
        report['status']='failed';report['error']=repr(e);raise
    finally:
        report['finished']=time.time();a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
