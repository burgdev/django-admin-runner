import 'core.just'

# 📋 Show changelog entries (version: current | unreleased | <x.y.z>) (default)
[default]
changelog version="current" unreleased="no" plain="no":
    #! ./.shell-wrapper.sh

    version="{{version}}"
    unreleased_flag=$(is_true "{{unreleased}}")
    plain_flag=$(is_true "{{plain}}")

    optional_header() { [[ "$plain_flag" == "true" ]] || header "$1" >&2; }

    content=""
    captured_version=""

    if [[ "$version" == "unreleased" || "$unreleased_flag" == "true" ]]; then
        content="$(uv run git-cliff --unreleased --bump --strip all | tail -n +2 || true)"
        bumped_version="$(uv run git-cliff --bumped-version | tr -d 'v')"
        captured_version="unreleased → ${bumped_version}"
    else
        input_file="CHANGELOG.md"
        if [[ ! -f "$input_file" ]]; then
            error "CHANGELOG.md not found."
            exit 1
        fi

        if [[ "$version" == "current" ]]; then
            pattern='^## \[(.*)\]'
        else
            pattern="^## \[(${version})\]"
        fi

        capture=false
        extracted=""
        while IFS= read -r line; do
            if [[ "$line" =~ $pattern ]] && [[ "$capture" == "false" ]]; then
                captured_version="${BASH_REMATCH[1]}"
                capture=true
                continue
            fi
            if [[ "$capture" == "true" ]]; then
                [[ "$line" =~ ^##\ \[.*\] ]] && break
                extracted+="${line}"$'\n'
            fi
        done < "$input_file"

        content="$(echo "$extracted" | sed '/^[[:space:]]*$/d')"
    fi

    if [[ -z "$content" ]]; then
        optional_header "Nothing found for '${version}'"
        exit 1
    fi

    optional_header "Changelog for '${captured_version}'"
    echo "$content"

# ❓ Show help
[private]
help task="":
    @just --list changelog
