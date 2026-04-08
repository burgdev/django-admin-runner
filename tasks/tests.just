import 'core.just'

# 📋 Run tests (default)
[default]
tests cov="no":
    #! ./.shell-wrapper.sh
    header "Running tests..."
    if [[ "$(is_true "{{cov}}")" == "true" ]]; then
        uv run --group test pytest --cov=django_admin_runner --cov-report=term-missing --cov-report=html
    else
        uv run --group test pytest -v
    fi

# ❓ Show help
[private]
help task="":
    @just --list tests
