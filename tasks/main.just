import 'core.just'

# ⚡ Code quality tasks (lint, fix, types, ...)
mod check
# 📋 Run tests (pytest)
mod tests
# 📚 Documentation tasks (build, serve, ...)
mod docs
# 📦 Project tasks (install, release, build, ...)
mod project
# 📝 Changelog tasks
mod changelog

# ❓ Show help
[default]
help:
    @echo "Run tasks with 'just <group> <task> [params]'."
    @echo ""
    @echo "Examples:"
    @echo "    just check"
    @echo "    just project release"
    @echo "    just tests cov=yes"
    @echo "    just docs serve"
    @echo "    just changelog"
    @echo ""
    @just --list

# 📦 Alias for 'just project install'
[group("aliases")]
install:
    just project install

# 🚀 Alias for 'just project release'
[group("aliases")]
release:
    just project release
