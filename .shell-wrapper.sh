#!/usr/bin/env bash
# Shell wrapper providing colored output helpers for just tasks.
#
# Used in two ways:
#   1. As the just shell:  set shell := ["./.shell-wrapper.sh", "-c"]
#      just calls:  .shell-wrapper.sh -c "command string"
#
#   2. As a shebang interpreter in multi-line recipes:  #! ./.shell-wrapper.sh
#      just calls:  .shell-wrapper.sh /path/to/temp_script

BOLD='\033[1m'
NORMAL='\033[0m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'

header()  { echo -e "\n${BOLD}${CYAN}▶ ${1}${NORMAL}\n"; }
info()    { echo -e "  ${BLUE}ℹ ${1}${NORMAL}"; }
success() { echo -e "  ${GREEN}✔ ${1}${NORMAL}"; }
warn()    { echo -e "  ${YELLOW}⚠ ${1}${NORMAL}"; }
error()   { echo -e "  ${RED}✘ ${1}${NORMAL}" >&2; }

is_true() {
    local val="${1,,}"
    [[ "$val" == "yes" || "$val" == "true" || "$val" == "1" ]] && echo "true" || echo "false"
}

if [[ "${1}" == "-c" ]]; then
    # Single-line recipe via 'set shell'
    eval "${2}"
else
    # Multi-line shebang recipe: source the temp script with our functions in scope
    export -f header info success warn error is_true
    export BOLD NORMAL BLUE GREEN YELLOW RED CYAN
    bash "${1}"
fi
