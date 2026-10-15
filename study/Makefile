.PHONY: all corpus run compress analyse paper clean-paper

PY = uv run python
EXPERIMENTS = e0_baseline e5_overhead e1_overlap e3_effects e4_group e6_flaky e2_budget

all: analyse paper

corpus:
	$(PY) -m harness.corpus

# Run one experiment with `make run E=e1_overlap`, or all of them in the documented order.
run:
ifdef E
	$(PY) -m experiments.$(E)
else
	for e in $(EXPERIMENTS); do $(PY) -m experiments.$$e || exit 1; done
endif

# Gzip raw files of finished runs. Do not run while an experiment is in progress.
compress:
	$(PY) -c "from harness.records import compress_finished; compress_finished()"

analyse:
	$(PY) -m analysis.run

paper:
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null \
	  && bibtex main >/dev/null \
	  && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null \
	  && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null \
	  && cp main.pdf test-suite-auditor-study.pdf
	@echo "paper/test-suite-auditor-study.pdf"

clean-paper:
	cd paper && rm -f *.aux *.log *.bbl *.blg *.out main.pdf
