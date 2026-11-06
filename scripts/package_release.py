# SPDX-License-Identifier: Apache-2.0
"""Create the font-only bundle from an explicit public-file allowlist."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
from _common import ROOT,read,rec

def main():
    policy=read(ROOT/'release.json');version=policy['version'];published=read(ROOT/'fonts/manifest.json')
    assert published['version']==version and published['fontVersion']==policy['fontVersion'], 'Promote the verified matching production fonts before packaging.'
    dest=ROOT/'dist';dest.mkdir(exist_ok=True)
    archive=dest/policy['archiveName'];assert archive.name==policy['archiveName'] and not archive.exists()
    files=[ROOT/'INSTALL.md',ROOT/'LICENSE',ROOT/'NOTICE.md',ROOT/'release.json']
    for folder in ['fonts','licenses','companions','examples','docs']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
    stamp=datetime.fromtimestamp(policy['sourceDateEpoch'],timezone.utc);names=[]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as package:
        for p in sorted(files):
            name='README.md' if p.name=='INSTALL.md' else p.relative_to(ROOT).as_posix()
            assert name not in names;names.append(name)
            info=zipfile.ZipInfo(name,(stamp.year,stamp.month,stamp.day,stamp.hour,stamp.minute,stamp.second));info.external_attr=0o100644<<16
            package.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        actual={r.filename:package.read(r) for r in package.infolist()}
        for row in read(ROOT/'fonts/checksums.json')['files']:
            data=actual[row['path']];assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        assert sum(n.endswith(('.ttf','.woff2')) for n in actual)==32
        assert not any(n.startswith(('build/','sources/','.git/','.venv/','web/')) for n in actual)
    receipt={'spdxLicense':'CC-BY-4.0','version':version,'archive':rec(archive),'files':names,'fontFiles':32,'allFontDigestsVerified':True}
    (dest/'artifact.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    (dest/'SHA256SUMS').write_text(rec(archive)['sha256']+'  '+archive.name+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'archive':rec(archive),'files':len(names),'fontFiles':32}))

if __name__=='__main__':main()
