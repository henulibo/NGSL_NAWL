PYTHON ?= python3

.PHONY: build test test-python test-js check-release release

build:
	$(PYTHON) vocab-data/build.py
	$(PYTHON) server/build_web.py

test: test-python test-js

test-python:
	$(PYTHON) -m pytest -q

test-js:
	node --test tests/*.test.js

check-release:
	$(PYTHON) scripts/package_public_release.py --check

release:
	$(PYTHON) scripts/package_public_release.py
