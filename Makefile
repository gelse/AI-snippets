.DEFAULT_GOAL := help

PYTHON ?= python3
NODE   ?= node
VENV    = .venv
STAMP   = $(VENV)/.stamp
NPM_STAMP = scripts/.npm-stamp

.PHONY: help verify zoo kilo opencode claude all clean \
        check-node verify-js zoo-js kilo-js opencode-js claude-js all-js \
        install-zoo-global install-zoo-local \
        install-zoo-global-skills install-zoo-global-agents \
        install-zoo-local-skills install-zoo-local-agents

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  %-30s %s\n", $$1, $$2}'

$(STAMP): ## Bootstrap venv (idempotent)
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet pyyaml ruff
	touch $(STAMP)

verify: $(STAMP) ## Validate modes.json and round-trip check
	$(VENV)/bin/python scripts/verify.py
	$(VENV)/bin/ruff check scripts/ skills/

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

# ── Node.js counterparts ────────────────────────────────────────────

$(NPM_STAMP): scripts/package.json
	cd scripts && npm install
	@touch $(NPM_STAMP)

check-node: ## Guard: verify node is available
	@command -v $(NODE) >/dev/null 2>&1 || \
		(echo "FAIL: node is not installed or not on PATH — install Node.js to use the *-js targets" && exit 1)

verify-js: check-node $(NPM_STAMP) ## Validate modes.json and round-trip check (Node.js)
	cd scripts && $(NODE) verify.mjs

zoo-js: verify-js ## Generate Zoo Code artifacts (Node.js)
	cd scripts && $(NODE) generate.mjs zoo

kilo-js: verify-js ## Generate Kilo Code artifacts (Node.js)
	cd scripts && $(NODE) generate.mjs kilo

opencode-js: verify-js ## Generate OpenCode artifacts (Node.js)
	cd scripts && $(NODE) generate.mjs opencode

claude-js: verify-js ## Generate Claude Code artifacts (Node.js)
	cd scripts && $(NODE) generate.mjs claude

all-js: zoo-js kilo-js opencode-js claude-js ## Generate all tool artifacts (Node.js)

# ── Zoo install targets ─────────────────────────────────────────────

install-zoo-global: install-zoo-global-skills install-zoo-global-agents ## Install zoo skills and agents globally

install-zoo-local: install-zoo-local-skills install-zoo-local-agents ## Install zoo skills and agents locally

install-zoo-global-skills: zoo ## Install zoo skills globally
	@mkdir -p $(HOME)/.roo/skills
	@for f in output/zoo/skills/*.md; do \
		n=$$(basename "$$f" .md); \
		mkdir -p "$(HOME)/.roo/skills/$$n"; \
		cp "$$f" "$(HOME)/.roo/skills/$$n/SKILL.md"; \
		if [ -d "output/zoo/skills/$$n" ]; then \
			cp output/zoo/skills/$$n/* "$(HOME)/.roo/skills/$$n/" || true; \
		fi; \
	done

install-zoo-global-agents: zoo ## Install zoo agents globally
	@mkdir -p $(HOME)/.roo
	@echo "⚠  Overwriting $(HOME)/.roo/custom_modes.yaml with generated modes"
	@cp output/zoo/.roomodes $(HOME)/.roo/custom_modes.yaml

install-zoo-local-skills: zoo ## Install zoo skills locally
	@mkdir -p .roo/skills
	@for f in output/zoo/skills/*.md; do \
		n=$$(basename "$$f" .md); \
		mkdir -p ".roo/skills/$$n"; \
		cp "$$f" ".roo/skills/$$n/SKILL.md"; \
		if [ -d "output/zoo/skills/$$n" ]; then \
			cp output/zoo/skills/$$n/* ".roo/skills/$$n/" || true; \
		fi; \
	done

install-zoo-local-agents: zoo ## Install zoo agents locally
	@cp output/zoo/.roomodes .roomodes
