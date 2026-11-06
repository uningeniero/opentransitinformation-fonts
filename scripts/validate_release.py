# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry point for current serialized UFO-production checks."""
from pathlib import Path
import argparse,sys
from validate_ufo import validate

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path)
    sys.exit(0 if validate(parser.parse_args().folder.resolve()) else 1)
