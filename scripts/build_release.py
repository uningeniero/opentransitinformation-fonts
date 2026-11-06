# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry point for the current editable-UFO production build."""
from pathlib import Path
import argparse
from build_ufo import main
from _common import ROOT,read

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build'/('production-'+read(ROOT/'release.json')['version']))
    main(parser.parse_args().output_dir)
