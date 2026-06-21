# bombom — local dev convenience targets
.PHONY: install index demo serve test lint

install:          ## editable install with dev extras
	pip install -e ".[dev]"

index:            ## one-time: init catalog submodule + build the SQLite index
	bombom catalog sync && bombom catalog reindex

demo:             ## seed a realistic demo workspace and serve it (full local test)
	python scripts/demo.py demo-workspace
	bombom serve --root demo-workspace

serve:            ## serve the current dir as a workspace
	bombom serve

test:             ## run the test suite
	pytest -q

lint:             ## lint backend
	ruff check bombom tests
