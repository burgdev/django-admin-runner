import 'core.just'

# ▶️  Run all checks: lock + lint (default)
[default]
all: lock lint
    @info "Tests are not run separately — use 'just tests'."

# 🔒 Check uv lock file is up to date
lock:
    @header "Checking lock file..."
    uv lock --locked
    @success "🏁 Lock file OK!"

# 🧹 Lint with pre-commit (ruff + hooks)
lint:
    @header "Linting..."
    uv run pre-commit run -a
    @success "🏁 Linting passed!"

# 🪄 Auto-fix with ruff
fix:
    @header "Fixing..."
    uv run ruff check --fix .
    uv run ruff format .
    @success "🏁 Fixes applied!"

# 🔍 Static type checking
types:
    @header "Type checking..."
    uv run pyright src
    @success "🏁 Type checking passed!"

# ❓ Show help
[private]
help task="":
    @just --list check
