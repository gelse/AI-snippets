.DEFAULT_GOAL := help

PYTHON ?= python3
VENV    = .venv
STAMP   = $(VENV)/.stamp

.PHONY: help verify zoo kilo opencode claude all clean

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  %-15s %s\n", $$1, $$2}'

$(STAMP): ## Bootstrap venv (idempotent)
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet pyyaml ruff
	touch $(STAMP)

verify: $(STAMP) ## Validate modes.json and round-trip check
	$(VENV)/bin/python scripts/verify.py
	$(VENV)/bin/ruff check scripts/

zoo: verify ## Generate Zoo Code artifacts
	$(VENV)/bin/python scripts/generate.py zoo

kilo: verify ## Generate Kilo Code artifacts
	$(VENV)/bin/python scripts/generate.py kilo

opencode: verify ## Generate OpenCode artifacts
	$(VENV)/bin/python scripts/generate.py opencode

claude: verify ## Generate Claude Code artifacts
	$(VENV)/bin/python scripts/generate.py claude

all: zoo kilo opencode claude ## Generate all tool artifacts

clean: ## Remove generated output
	rm -rf output
