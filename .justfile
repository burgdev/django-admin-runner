# django-admin-runner justfile

# Install all dev dependencies
install:
    uv sync --all-extras

# Run tests
test *args:
    uv run pytest {{args}}

# Run tests with coverage
cov:
    uv run pytest --cov=django_admin_runner --cov-report=term-missing --cov-report=html

# Run a specific example app
example name:
    cd examples/{{name}} && uv run python manage.py runserver

# Lint
lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

# Fix lint issues
fmt:
    uv run ruff check --fix src tests
    uv run ruff format src tests

# Build docs locally with live reload
docs:
    uv run mkdocs serve

# Build docs for deployment
docs-build:
    uv run mkdocs build

# Bump version (patch|minor|major)
bump part="patch":
    uv run bump-my-version bump {{part}}

# Build distribution
build:
    uv build

# Publish to PyPI
publish:
    uv publish

# Generate changelog from git history
changelog:
    git cliff -o CHANGELOG.md

# Run pre-commit on all files
check:
    uv run pre-commit run --all-files
