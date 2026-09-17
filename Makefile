.DEFAULT_GOAL := help

PYTHON ?= python3
NODE   ?= node
NPM    ?= npm
VENV    = .venv
STAMP   = $(VENV)/.stamp
NPM_STAMP = .npm-stamp

.PHONY: help verify zoo kilo opencode claude manifest all clean \
        check-node package-npx \
        package-npx-zoo package-npx-kilo package-npx-opencode package-npx-claude \
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

verify: $(STAMP) ## Validate modes.json, round-trip check, and TS build (node-optional)
	$(VENV)/bin/python scripts/verify.py
	$(VENV)/bin/ruff check scripts/ skills/
	@if command -v $(NODE) >/dev/null 2>&1 && command -v $(NPM) >/dev/null 2>&1; then \
		$(MAKE) $(NPM_STAMP) && \
		$(NPM) run typecheck && \
		$(NPM) run build && \
		TMPHOME=$$(mktemp -d) && \
		HOME=$$TMPHOME $(NODE) dist/cli.cjs install zoo --global --dry-run; \
		status=$$?; rm -rf "$$TMPHOME"; exit $$status; \
	else \
		echo "SKIP: node not available"; \
	fi

zoo: verify ## Generate Zoo Code artifacts
	$(VENV)/bin/python scripts/generate.py zoo

kilo: verify ## Generate Kilo Code artifacts
	$(VENV)/bin/python scripts/generate.py kilo

opencode: verify ## Generate OpenCode artifacts
	$(VENV)/bin/python scripts/generate.py opencode

claude: verify ## Generate Claude Code artifacts
	$(VENV)/bin/python scripts/generate.py claude

all: zoo kilo opencode claude manifest ## Generate all tool artifacts

manifest: verify ## Generate install-manifest.json
	$(VENV)/bin/python scripts/generate.py manifest

clean: ## Remove generated output
	rm -rf output

# ── npm packaging ───────────────────────────────────────────────────

$(NPM_STAMP): package.json
	$(NPM) install
	@touch $(NPM_STAMP)

check-node: ## Guard: verify node and npm are available
	@command -v $(NODE) >/dev/null 2>&1 && command -v $(NPM) >/dev/null 2>&1 || \
		(echo "FAIL: node and npm are required — install Node.js to use package-npx targets" && exit 1)

package-npx: check-node $(NPM_STAMP) $(STAMP) ## Build and pack the npm package
	$(VENV)/bin/python scripts/generate.py zoo
	$(VENV)/bin/python scripts/generate.py kilo
	$(VENV)/bin/python scripts/generate.py opencode
	$(VENV)/bin/python scripts/generate.py claude
	$(VENV)/bin/python scripts/generate.py manifest
	$(NPM) run build
	@# Place dist/release.js alongside the release skill in each embedded tool tree
	cp dist/release.js skills-embedded/zoo/skills/release/release.js
	cp dist/release.js skills-embedded/kilo/skills/release/release.js
	cp dist/release.js skills-embedded/opencode/skill/release/release.js
	cp dist/release.js skills-embedded/claude/skills/release/release.js
	$(NPM) pack --pack-destination dist/

package-npx-zoo: package-npx ## Smoke-test: install zoo via built package
	$(NODE) dist/cli.cjs install zoo --global --yes

package-npx-kilo: package-npx ## Smoke-test: install kilo via built package
	$(NODE) dist/cli.cjs install kilo --global --yes

package-npx-opencode: package-npx ## Smoke-test: install opencode via built package
	$(NODE) dist/cli.cjs install opencode --global --yes

package-npx-claude: package-npx ## Smoke-test: install claude via built package
	$(NODE) dist/cli.cjs install claude --global --yes

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
