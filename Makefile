
# make test <target>: run a specified test
# make cover: run all tests and generate code coverage
SHELL:=/bin/bash

ifeq (test,$(firstword $(MAKECMDGOALS)))
  # use the rest as arguments for "test"
  RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  # ...and turn them into do-nothing targets
  $(eval $(RUN_ARGS):;@:)
endif

# `make test <test-name>` will run a specific test
.PHONY: test
test:
	coverage run -m tests.$(RUN_ARGS)_test
	coverage html --omit "venv/*,*_test.py,tests/*"
	@#open htmlcov/index.html
	@printf "%-60s %10s\n" $(shell grep pc_cov ./htmlcov/*.html | sed 's/<span.*">//' | sed 's=</span>==') | sort -V

.PHONY: cover
cover:
	@coverage run -m tests -vv
	@coverage html --omit "venv/*,*_test.py,tests/*,*graph.py,*guiserver.py"
	@echo ""
	@printf "%-60s %10s\n" $(shell grep pc_cov ./htmlcov/mp*.html | sed 's/<span.*">//' | sed 's=</span>==') | sort -V
	@echo ""
	@printf "Coverage Report: %s\n" $(shell grep pc_cov ./htmlcov/index.html | sed 's/<span.*">//' | sed 's=</span>==') | sort -V

.PHONY: demo
demo:
	 python demo/tankclient.py

.PHONY: demo_server
demo_server:
	unbuffer python demo/tankserver.py

