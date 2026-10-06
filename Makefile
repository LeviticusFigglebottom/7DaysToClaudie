# Hollowmere — task runner. `make help` lists targets.
# Toolchain is pinned in tools/versions.env and installed into .tools/ by `make setup`.
# Override tool paths with e.g. `make test GODOT=/usr/bin/godot`.

SHELL := /bin/bash
ROOT := $(abspath .)
GAME := $(ROOT)/game
TOOLS_DIR := $(ROOT)/.tools

GODOT ?= $(shell if [ -x $(TOOLS_DIR)/godot/godot ]; then echo $(TOOLS_DIR)/godot/godot; else command -v godot; fi)
BLENDER ?= $(shell if [ -x $(TOOLS_DIR)/blender/blender ]; then echo $(TOOLS_DIR)/blender/blender; else command -v blender; fi)
PYTHON ?= $(shell if [ -x $(TOOLS_DIR)/venv/bin/python ]; then echo $(TOOLS_DIR)/venv/bin/python; else command -v python3; fi)
# Software-rendered display for screenshots/bakes on headless machines (Mesa lavapipe Vulkan).
XVFB ?= xvfb-run -a -s "-screen 0 1920x1080x24"
JOBS ?= $(shell nproc 2>/dev/null || echo 4)
LOCK := flock $(ROOT)/build/.godot.lock
GODOT_HEADLESS := $(LOCK) $(GODOT) --headless --path $(GAME)

.PHONY: smoke tour export render-check probe-lab check preview help setup setup-godot setup-blender setup-python fonts vendor-gut \
        assets assets-force assets-list assets-clean assets-determinism bake \
        import validate test test-unit test-integration run run-slice editor screenshots ci clean poi-preview

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: setup-godot setup-blender setup-python ## Install pinned Godot, Blender and the Python venv into .tools/

setup-godot:
	@tools/setup/install_godot.sh

setup-blender:
	@tools/setup/install_blender.sh

setup-python:
	@tools/setup/install_python.sh

fonts: ## Re-fetch open-licensed fonts (pinned by SHA-256)
	@python3 tools/setup/fetch_fonts.py

vendor-gut: ## Re-vendor GUT at the pinned version
	@python3 tools/setup/vendor_gut.py

assets: ## Regenerate all procedural assets (incremental) + Godot bakes (icons, impostors)
	@$(PYTHON) tools/build_assets.py --jobs $(JOBS) --blender "$(BLENDER)"
	@$(MAKE) --no-print-directory import
	@$(MAKE) --no-print-directory bake

assets-force: ## Regenerate every asset from scratch
	@$(PYTHON) tools/build_assets.py --force --jobs $(JOBS) --blender "$(BLENDER)"
	@$(MAKE) --no-print-directory import
	@$(MAKE) --no-print-directory bake

assets-list: ## List asset tasks and their state
	@$(PYTHON) tools/build_assets.py --list

assets-clean: ## Delete game/assets/generated
	@$(PYTHON) tools/build_assets.py --clean

assets-determinism: ## Rebuild assets into a scratch dir and compare hashes with the manifest
	@$(PYTHON) tools/build_assets.py --check-determinism --jobs $(JOBS) --blender "$(BLENDER)"

bake: ## Godot-side bakes that need the renderer (item icons, tree impostors, region data)
	@mkdir -p $(ROOT)/build; if [ -f $(GAME)/src/tools/cli/bake.gd ]; then $(LOCK) $(XVFB) $(GODOT) --path $(GAME) --rendering-driver vulkan --audio-driver Dummy -s res://src/tools/cli/bake.gd; fi
	@$(MAKE) --no-print-directory import

import: ## Import project resources headless (required before tests on a fresh clone)
	@mkdir -p $(ROOT)/build && $(GODOT_HEADLESS) --import > $(ROOT)/build/import.log 2>&1 || (cat $(ROOT)/build/import.log; exit 1)
	@# Models imported before their material library existed keep placeholder materials: redo them.
	@$(GODOT_HEADLESS) -s res://src/tools/cli/verify_imports.gd >> $(ROOT)/build/import.log 2>&1; \
	if [ $$? -eq 2 ]; then $(GODOT_HEADLESS) --import >> $(ROOT)/build/import.log 2>&1 || (cat $(ROOT)/build/import.log; exit 1); fi
	@echo "[import] ok"

smoke: ## Headless end-to-end run of the slice (world, trees, building, crafting, AI, Hum, save/load)
	@$(GODOT_HEADLESS) -s res://src/tools/cli/slice_smoke.gd

tour: ## Headless walk tour: the player runs into, hits and uses every kind of thing (crash hunt, ADR-0036)
	@$(GODOT_HEADLESS) -s res://src/tools/cli/walk_tour.gd -- $(TOUR_ARGS)

validate: ## Validate content, asset references and POIs
	@$(GODOT_HEADLESS) -s res://src/tools/cli/validate.gd -- $(VALIDATE_ARGS)

test: ## Run all GUT tests headless (JUnit XML in build/test-results)
	@mkdir -p $(ROOT)/build/test-results
	@$(GODOT_HEADLESS) -s res://addons/gut/gut_cmdln.gd -gexit -gdisable_colors -gjunit_xml_file=$(ROOT)/build/test-results/gut.xml

test-unit: ## Unit tests only
	@$(GODOT_HEADLESS) -s res://addons/gut/gut_cmdln.gd -gexit -gdisable_colors -gdir=res://tests/unit -gconfig=

test-integration: ## Integration tests only
	@$(GODOT_HEADLESS) -s res://addons/gut/gut_cmdln.gd -gexit -gdisable_colors -gdir=res://tests/integration -gconfig=

run: ## Run the game
	@$(GODOT) --path $(GAME)

run-slice: ## Start the vertical slice directly
	@$(GODOT) --path $(GAME) -- --new-game --mode slice

editor: ## Open the Godot editor
	@$(GODOT) --path $(GAME) --editor

screenshots: ## Capture the screenshot suite into build/screenshots (software Vulkan under Xvfb)
	@mkdir -p $(ROOT)/build/screenshots
	@# The watchdog ends a run whose engine shutdown hangs after "SHOT done" (it would hold the lock).
	@$(LOCK) $(ROOT)/tools/qa_watchdog.sh "SHOT done" $(XVFB) $(GODOT) --path $(GAME) --rendering-driver vulkan --audio-driver Dummy --resolution 1600x900 -s res://src/tools/cli/screenshots.gd -- --out $(ROOT)/build/screenshots $(SHOTS_ARGS)

ci: ## Everything CI runs: setup, assets, import, validate (strict), tests
	@$(MAKE) --no-print-directory setup
	@$(MAKE) --no-print-directory assets
	@$(MAKE) --no-print-directory validate VALIDATE_ARGS=--strict-assets
	@$(MAKE) --no-print-directory test

export: ## Package Windows and Linux builds with the generated assets into build/export/*.zip (ADR-0036): make export [EXPORT_TARGETS="windows linux"]
	@mkdir -p $(ROOT)/build/export
	@GODOT="$(GODOT)" LOCK="$(LOCK)" tools/export/export.sh $(EXPORT_TARGETS)

render-check: ## Render town views (software Vulkan) and fail on renderer errors such as probe atlas overflow (ADR-0036): [RENDER_CHECK_SHOTS=a,b]
	@GODOT="$(GODOT)" LOCK="$(LOCK)" tools/qa/render_check.sh $(RENDER_CHECK_SHOTS)

probe-lab: ## How this Godot treats interior reflection probes switched off and on (hide/detach/base); re-run after a Godot upgrade (TD-044)
	@cd $(ROOT)/tools/probe_lab && for m in hide detach base; do \
		xvfb-run -a -s "-screen 0 640x480x24" $(GODOT) --path . --rendering-driver vulkan --audio-driver Dummy --resolution 320x240 \
			-s res://probe_lab.gd -- $$m 2>&1 | grep -E "LAB2|FATAL|atlas index invalid" | head -3; done

clean: ## Remove build output (keeps .tools and generated assets)
	rm -rf $(ROOT)/build $(GAME)/.godot

preview: import ## Render generated models in-engine for visual QA: make preview MODELS="rocks/boulder_a rocks/boulder_b" [PREVIEW_ARGS="--grid"]
	@mkdir -p $(ROOT)/build/previews
	@$(LOCK) $(XVFB) $(GODOT) --path $(GAME) --rendering-driver vulkan --audio-driver Dummy -s res://src/tools/cli/preview_asset.gd -- --out $(ROOT)/build/previews $(PREVIEW_ARGS) $(MODELS) 2>&1 | grep -E "PREVIEW|ERROR|SCRIPT ERROR" || true

poi-preview: ## Render POIs for layout QA (cut-away plans + exteriors): make poi-preview POI="mile9_diner pell_pharmacy" [POI_ARGS="--size 1600x900 --no-exterior"]
	@mkdir -p $(ROOT)/build/poi_preview
	@$(LOCK) $(XVFB) $(GODOT) --path $(GAME) --rendering-driver vulkan --audio-driver Dummy -s res://src/tools/cli/poi_preview.gd -- --out $(ROOT)/build/poi_preview $(POI_ARGS) $(POI) 2>&1 | grep -E "POI_PREVIEW|ERROR|SCRIPT ERROR" || true

check: ## Fast compile check of every script (no gameplay)
	@$(GODOT_HEADLESS) -s res://src/tools/cli/check_scripts.gd 2>&1 | grep -E "check\]|SCRIPT ERROR|Parse Error|Compile Error|at: " | grep -v "^$$" | head -60
