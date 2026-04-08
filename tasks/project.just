import 'core.just'

# 📦 Install the uv environment and pre-commit hooks
install sync_args="--all-groups --all-extras":
    @header "Installing project dependencies..."
    cd {{justfile_dir()}}; uv sync {{sync_args}}
    cd {{justfile_dir()}}; uv run pre-commit install

# 🚀 Prepare a release: update CHANGELOG and bump version
release add_tag="no" dry="no" unreleased="yes":
    #! ./.shell-wrapper.sh
    header "Preparing release..."
    new_tag=$(uv run git-cliff --bumped-version)
    new_version="${new_tag#v}"

    if [[ "$(is_true "{{dry}}")" == "true" ]]; then
        header "Changelog preview"
        if [[ "$(is_true "{{unreleased}}")" == "true" ]]; then
            uv run git-cliff --bump --unreleased
        else
            uv run git-cliff --bump
        fi
    else
        uv run git-cliff --bump -u --prepend CHANGELOG.md
        uv run bump2version --new-version "$new_version" patch
        success "Bumped to version '$new_version' (tag '$new_tag')."
        warn "Review CHANGELOG.md, then commit and tag the release."
        if [[ "$(is_true "{{add_tag}}")" == "true" ]]; then
            git tag -f "$new_tag"
            success "Created tag '$new_tag'. Push with: git push origin '$new_tag'"
        fi
    fi

# 🔢 Print current or next project version
version next="no":
    #! ./.shell-wrapper.sh
    version=$(grep -E '^version\s*=' {{justfile_dir()}}/pyproject.toml | head -1 | cut -d'"' -f2)
    if [[ "$(is_true "{{next}}")" == "true" ]]; then
        uv run git-cliff --bumped-version | tr -d 'v'
    else
        echo "$version"
    fi

# 🏗️ Build distribution packages
build:
    @header "Building distribution..."
    uv build
    @success "🏁 Build done! Artifacts in dist/"

# 🚀 Publish to PyPI
publish:
    @header "Publishing to PyPI..."
    uv publish
    @success "🏁 Published!"

# ❓ Show help
[private]
[default]
help task="":
    @just --list project
