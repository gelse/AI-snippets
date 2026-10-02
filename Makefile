.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
STAMP   = $(VENV)/.stamp
ZOO_GLOBALSTORAGE ?= $(HOME)/.config/Code/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml
OPENCODE_CONFIG_HOME ?= $(if $(XDG_CONFIG_HOME),$(XDG_CONFIG_HOME),$(HOME)/.config)

.PHONY: help check-py verify zoo kilo opencode manifest all clean \
        install-zoo-global install-zoo-local \
        install-zoo-global-skills install-zoo-global-agents \
        install-zoo-local-skills install-zoo-local-agents \
        install-opencode-global

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

check-py: $(STAMP) ## Validate modes.json, lint scripts/skills (Python only)
	$(VENV)/bin/python scripts/verify.py
	$(VENV)/bin/ruff check scripts/ skills/

verify: check-py ## Alias of check-py (legacy name, Python-only)

zoo: check-py ## Generate Zoo Code artifacts
	$(VENV)/bin/python scripts/generate.py zoo

kilo: check-py ## Generate Kilo Code artifacts
	$(VENV)/bin/python scripts/generate.py kilo

opencode: check-py ## Generate OpenCode artifacts
	$(VENV)/bin/python scripts/generate.py opencode

all: zoo kilo opencode manifest ## Generate all tool artifacts

manifest: check-py ## Generate install-manifest.json
	$(VENV)/bin/python scripts/generate.py manifest

clean: ## Remove generated output
	rm -rf output

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

install-zoo-global-agents: zoo ## Install zoo agents globally to ~/.roo and merge into Zoo Code globalStorage
	@mkdir -p $(HOME)/.roo
	@echo "⚠  Overwriting $(HOME)/.roo/custom_modes.yaml with generated modes"
	@cp output/zoo/.roomodes $(HOME)/.roo/custom_modes.yaml
	@if [ -d "$(dir $(ZOO_GLOBALSTORAGE))" ]; then \
		echo "Merging generated modes into $(ZOO_GLOBALSTORAGE)"; \
		$(VENV)/bin/python scripts/merge-modes.py output/zoo/.roomodes "$(ZOO_GLOBALSTORAGE)"; \
	else \
		echo "SKIP: Zoo Code globalStorage not found at $(dir $(ZOO_GLOBALSTORAGE))"; \
	fi

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

# ── OpenCode install targets ───────────────────────────────────────

install-opencode-global: opencode ## Install opencode agents and skills globally
	@mkdir -p $(OPENCODE_CONFIG_HOME)/opencode/agents
	@cp output/opencode/agents/*.md $(OPENCODE_CONFIG_HOME)/opencode/agents/
	@mkdir -p $(OPENCODE_CONFIG_HOME)/opencode/skills
	@for f in output/opencode/skill/*.md; do \
		n=$$(basename "$$f" .md); \
		mkdir -p "$(OPENCODE_CONFIG_HOME)/opencode/skills/$$n"; \
		cp "$$f" "$(OPENCODE_CONFIG_HOME)/opencode/skills/$$n/SKILL.md"; \
		if [ -d "output/opencode/skill/$$n" ]; then \
			cp output/opencode/skill/$$n/* "$(OPENCODE_CONFIG_HOME)/opencode/skills/$$n/" || true; \
		fi; \
	done
