# SPDX-License-Identifier: Apache-2.0
"""Fetch a digest-pinned official tool into the ignored build directory."""
from pathlib import Path
import hashlib,os,platform,shutil,subprocess,tarfile,zipfile
from _common import ROOT,read

def main():
    windows=platform.system()=='Windows'
    marker='pc-windows-gnu' if windows else 'unknown-linux-gnu'
    row=next(r for r in read(ROOT/'tools/fontspector.json')['assets'] if marker in r['name'])
    directory=ROOT/'build/tools';directory.mkdir(parents=True,exist_ok=True);archive=directory/row['name']
    if not archive.exists():
        temporary=archive.with_suffix(archive.suffix+'.download')
        subprocess.run(['curl.exe' if windows else 'curl','--fail','--location','--silent','--show-error','--output',str(temporary),row['url']],check=True)
        assert temporary.stat().st_size==row['bytes'] and hashlib.sha256(temporary.read_bytes()).hexdigest()==row['sha256']
        temporary.rename(archive)
    assert archive.stat().st_size==row['bytes'] and hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256']
    unpacked=directory/'fontspector-1.9.0'
    if not unpacked.exists():
        unpacked.mkdir()
        if windows:
            with zipfile.ZipFile(archive) as source:
                for name in source.namelist():(unpacked/name).resolve().relative_to(unpacked.resolve())
                source.extractall(unpacked)
        else:
            with tarfile.open(archive) as source:source.extractall(unpacked,filter='data')
    executable=next(unpacked.rglob('fontspector.exe' if windows else 'fontspector'))
    if not windows:executable.chmod(executable.stat().st_mode|0o111)
    print(executable.relative_to(ROOT).as_posix())

if __name__=='__main__':main()
