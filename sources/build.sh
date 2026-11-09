#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
exec "${PYTHON:-python3}" build.py build "$@"
