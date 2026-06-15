# explainer-engine — chunked render driver
# Usage:
#   make render SPEC=specs/universe.json
#   make preview SPEC=specs/universe.json FRAME=240
#   make clean

SPEC ?= specs/universe.json
CHUNK ?= 750
PY ?= python3

# total frames computed by the engine
TOTAL := $(shell $(PY) -c "import sys;sys.path.insert(0,'.');from engine import spec as s;sp=s.load('$(SPEC)');print(int(round(sp.total_duration()*sp.fps)))")

.PHONY: render preview audio assemble clean frames

render: frames assemble

frames:
	@echo "Rendering $(TOTAL) frames in chunks of $(CHUNK)..."
	@start=0; while [ $$start -lt $(TOTAL) ]; do \
		end=$$((start + $(CHUNK))); \
		if [ $$end -gt $(TOTAL) ]; then end=$(TOTAL); fi; \
		echo ">> chunk [$$start, $$end)"; \
		$(PY) -m engine.render $(SPEC) $$start $$end || exit 1; \
		start=$$end; \
	done

assemble:
	@$(PY) -m engine.assemble $(SPEC)

preview:
	@$(PY) cli.py preview $(SPEC) --frame $(FRAME)

clean:
	@rm -rf out/frames/*.png out/_silent.mp4 out/_audio.wav out/final.mp4 out/preview_*.png
	@echo "cleaned."
