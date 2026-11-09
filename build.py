# SPDX-License-Identifier: Apache-2.0
"""Bootstrap the pinned environment and run the repository's real font build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent

def run(command, capture=False):
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, encoding='utf-8',
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bootstrap', 'build', 'validate', 'reproduce', 'qa', 'all', 'package'], nargs='?', default='build')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--qa-output-dir', type=Path)
    parser.add_argument('--family', choices=['all','sign','screen'], default='all')
    args = parser.parse_args()
    policy = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    tools = json.loads((ROOT / 'tools/production.json').read_text(encoding='utf-8'))
    actual_python = '.'.join(map(str, sys.version_info[:3]))
    if actual_python != tools['python']:
        parser.error('Use CPython ' + tools['python'] + '; observed ' + actual_python)
    environment = ROOT / 'build' / ('environment-' + policy['version'])
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    lock = ROOT / tools['dependencyLock']
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    marker = environment / 'dependency-lock.sha256'
    if not marker.exists() or marker.read_text(encoding='ascii').strip() != digest:
        run([str(python), '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:', '-r', str(lock)])
        marker.write_text(digest + '\n', encoding='ascii')
    suffix='' if args.family=='all' else '-'+args.family
    os.environ['PYTHONHASHSEED']='0'
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    output = (args.output_dir or ROOT / 'build' / ('production-' + policy['version']+suffix)).resolve()
    output.relative_to(ROOT / 'build')
    qa_output = (args.qa_output_dir or ROOT / 'build' / ('qa-production-' + policy['version']+suffix)).resolve()
    qa_output.relative_to(ROOT / 'build')
    if args.action in ['build', 'all']:
        run([str(python), 'scripts/build_ufo.py', '--output-dir', str(output), '--family', args.family])
    if args.action in ['validate', 'all']:
        run([str(python), 'scripts/validate_ufo.py', str(output), '--family', args.family])
    if args.action in ['reproduce', 'all']:
        comparison=output.with_name(output.name+'-reproduction')
        run([str(python), 'scripts/build_ufo.py', '--output-dir', str(comparison), '--family', args.family])
        run([str(python), 'scripts/check_reproduction.py', str(output), '--comparison-folder', str(comparison)])
    if args.action in ['qa', 'all']:
        binary = run([str(python), 'scripts/fetch_fontspector.py'], capture=True)
        run([str(python), 'scripts/run_fontspector.py', '--binary', binary, '--folder', str(output), '--output-dir', str(qa_output)])
    if args.action == 'package':
        run([str(python), 'scripts/package_release.py'])

if __name__ == '__main__':
    main()
