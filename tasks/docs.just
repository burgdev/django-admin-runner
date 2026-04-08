import 'core.just'

# 🌐 Serve docs locally with live reload (default)
[default]
serve port='8088':
    @header "Serving docs at localhost:{{port}}..."
    uv run --group docs mkdocs serve --dev-addr localhost:{{port}}

# 📦 Build docs
build:
    @header "Building docs..."
    uv run --group docs mkdocs build
    @success "🏁 Docs built in 'site/'."

# ❓ Show help
[private]
help task="":
    @just --list docs
