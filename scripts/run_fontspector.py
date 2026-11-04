# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import argparse,json,os,re,subprocess,sys
from _common import ROOT,read,rec

def main(binary,folder,output):
    os.chdir(ROOT);output.mkdir(parents=True,exist_ok=True)
    manifest=read(folder/'build-manifest.json');results=[]
    for role in ['screen','sign']:
        paths=[c['ttf']['path'] for c in manifest['cuts'] if c['role']==role]
        report=output/(role+'-googlefonts.json');log=output/(role+'-googlefonts.log')
        assert not report.exists() and not log.exists()
        command=[str(binary),'-p','googlefonts','-J','2','--timeout','20','--json',str(report.relative_to(ROOT)),*paths]
        with log.open('w',encoding='utf-8') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        assert report.exists(), 'Primary QA produced no report.'
        assert result.returncode in [0,1], result.returncode
        report_data=read(report);summary=report_data['summary'];policy=read(ROOT/'tools/qa-policy.json')['families'][role]
        unexpected=[]
        for sections in report_data['results'].values():
            for checks in sections.values():
                for check in checks:
                    for sub in check['subresults']:
                        if sub['severity'] in ['FATAL','ERROR']:unexpected.append((check['check_id'],sub['severity']))
                        if sub['severity']!='FAIL':continue
                        if sub['code'] not in policy['allowedFailCodes'].get(check['check_id'],[]):unexpected.append((check['check_id'],sub['code']))
                        if check['check_id']=='googlefonts/glyphsets/shape_languages':
                            languages=set(re.findall(r'\* ([a-zA-Z_]+) \(',sub['message']))
                            if not languages.issubset(policy['allowedFailedOrthographies']):unexpected.append(('new-orthography',sorted(languages)))
                            if role=='sign' and "Shaper didn't attach" in sub['message']:unexpected.append(('selected-attachment-regression',sub['message']))
                        if check['check_id']=='case_mapping':
                            for item in sub.get('metadata',[]):
                                problem=item.get('GlyphProblem')
                                if problem and [str(problem.get('actual')),str(problem.get('expected'))] not in policy['allowedCasePairs']:unexpected.append(('new-case-counterpart',problem))
        assert not unexpected, unexpected
        results.append({'role':role,'exitCode':result.returncode,'report':rec(report) if report.exists() else None,'log':rec(log),'summary':summary})
    receipt={'spdxLicense':'CC-BY-4.0','manifest':rec(folder/'build-manifest.json'),'toolVersion':subprocess.check_output([str(binary),'--version'],text=True,encoding='utf-8').strip(),'families':results}
    p=output/'fontspector-execution.json';p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(receipt))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();main(args.binary.resolve(),args.folder.resolve(),args.output_dir.resolve())
