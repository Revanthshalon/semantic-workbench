# Local equivalents of the jobs in .github/workflows/ci.yml.
# `make ci` runs them all, in the same flags the pipeline uses.

export CARGO_TERM_COLOR ?= always
export CARGO_INCREMENTAL ?= 0
export RUSTFLAGS ?= -D warnings

.DEFAULT_GOAL := help
.PHONY: help ci fmt fmt-fix clippy test deny coverage wiki

help: ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

ci: fmt clippy test deny coverage ## Run every pipeline job locally

fmt: ## Rust format check (rust-fmt)
	cargo fmt --all --check

fmt-fix: ## Apply rustfmt
	cargo fmt --all

clippy: ## Lints, warnings are errors (rust-clippy)
	cargo clippy --workspace --all-targets --all-features --locked -- -D warnings

test: ## Run the test suite (rust-test)
	cargo test --workspace --all-features --locked

deny: ## Dependency audit (rust-deny); needs cargo-deny
	@command -v cargo-deny >/dev/null || { echo "install it: cargo install cargo-deny --locked"; exit 1; }
	cargo deny check

coverage: ## Coverage report in target/coverage/ (rust-coverage); needs cargo-tarpaulin
	@command -v cargo-tarpaulin >/dev/null || { echo "install it: cargo install cargo-tarpaulin --locked"; exit 1; }
	cargo tarpaulin --config tarpaulin.ci.toml --locked

wiki: ## Render the wiki pages into target/wiki to preview them
	rm -rf target/wiki && mkdir -p target/wiki
	python3 -I scripts/publish_wiki.py . target/wiki
