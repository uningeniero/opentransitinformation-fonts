# SPDX-License-Identifier: Apache-2.0
"""Run and retain the complete primary profile without severity exceptions."""
from pathlib import Path
import argparse,json,os,subprocess,sys
from _common import ROOT,read,rec

def main(binary,folder,output):
    os.chdir(ROOT);output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=True)
    manifest=read(folder/'build-manifest.json');results=[]
    version=subprocess.check_output([str(binary),'--version'],text=True,encoding='utf-8').strip()
    assert read(ROOT/'tools/fontspector.json')['version'] in version
    for role,count in [('screen',8),('sign',4)]:
        paths=[c['ttf']['path'] for c in manifest['cuts'] if c['role']==role];assert len(paths)==count
        license_record=next(r['file'] for r in manifest['familyLicenses'] if r['role']==role)
        assert rec(ROOT/license_record['path'])==license_record
        report=output/(role+'-googlefonts.json');log=output/(role+'-googlefonts.log')
        assert not report.exists() and not log.exists()
        command=[str(binary),'-p','googlefonts','-J','2','--timeout','20','--json',str(report.relative_to(ROOT)),*paths,license_record['path']]
        with log.open('w',encoding='utf-8') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        assert result.returncode in [0,1] and report.exists(), 'Primary QA did not complete.'
        raw=read(report);findings=[]
        for filename,sections in raw['results'].items():
            for checks in sections.values():
                for check in checks:
                    for sub in check['subresults']:
                        if sub['severity'] in ['FAIL','ERROR','FATAL']:findings.append({'font':filename,'check':check['check_id'],**sub})
        row={'role':role,'command':command,'exitCode':result.returncode,'report':rec(report),'log':rec(log),'summary':raw['summary'],'unresolvedFindings':findings}
        results.append(row);print(json.dumps({'role':role,'summary':row['summary'],'report':row['report']}),flush=True)
    clean=not any(r['unresolvedFindings'] for r in results)
    receipt={'spdxLicense':'CC-BY-4.0','manifest':rec(folder/'build-manifest.json'),'toolVersion':version,'executable':rec(binary),
             'profile':'googlefonts','severityOverrides':False,'checkExclusions':[],'allReportedFindingsResolved':clean,'families':results}
    p=output/'fontspector-execution.json';p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'receipt':rec(p),'allReportedFindingsResolved':clean}));return clean

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();sys.exit(0 if main(args.binary.resolve(),args.folder.resolve(),args.output_dir.resolve()) else 1)
