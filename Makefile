# SPDX-License-Identifier: Apache-2.0
PYTHON ?= python3
.PHONY: all bootstrap build validate reproduce qa package
all bootstrap build validate reproduce qa package:
	$(PYTHON) build.py $@
