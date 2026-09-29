#!/usr/bin/env bash
# Image contract: the shipped image carries no tool to pivot with.
#
# A production image must contain nothing that lets an attacker who reaches
# code execution pivot: no bash, no perl, no busybox. The one exception is
# /bin/sh as dash, because the embedded PostgreSQL runs its own programs
# through it (initdb, pg_ctl); the contract checks that it is dash and
# nothing larger.
#
# The check runs the interpreter as the container entrypoint instead of asking
# the image to look at its own filesystem. `--pull=never` keeps docker from
# silently pulling a stale image from the registry when the local build is
# missing; that would test the wrong artefact.
#
# Usage: tests/image-contract.sh IMAGE...

set -uo pipefail

PASS=0
FAIL=0
declare -a FAILED_NAMES

_pass() { PASS=$((PASS + 1)); echo "  PASS  $1"; }
_fail() { FAIL=$((FAIL + 1)); FAILED_NAMES+=("$1"); echo "  FAIL  $1: $2"; }

# Absence of the interpreter is the pass condition, so the image itself must be
# present — otherwise every check would "pass" on a nonexistent image.
_image_exists() {
    local image="$1"
    if docker image inspect "${image}" > /dev/null 2>&1; then
        return 0
    fi
    _fail "${image}_image_exists" "image not built — run 'npm run build' first"
    return 1
}

_no_interpreter() {
    local image="$1" path="$2" name="$3"
    shift 3
    if docker run --rm --pull=never --entrypoint "${path}" "${image}" "$@" > /dev/null 2>&1; then
        _fail "${image}_no_${name}" "${path} exists — image is not headless"
    else
        _pass "${image}_no_${name}"
    fi
}

echo "==> Image contract: no tool to pivot with"

for image in "$@"; do
    _image_exists "${image}" || continue
    _no_interpreter "${image}" /bin/bash     bash    -c :
    _no_interpreter "${image}" /usr/bin/bash bash_usr -c :
    _no_interpreter "${image}" /bin/busybox  busybox ls /
    _no_interpreter "${image}" /usr/bin/perl perl    -e 1
    _no_interpreter "${image}" /usr/bin/apt-get apt  --version
    # /bin/sh exists for PostgreSQL, and it is dash and nothing else
    if docker run --rm --pull=never --entrypoint /usr/bin/dash "${image}" \
        -c 'test /bin/sh -ef /usr/bin/dash' > /dev/null 2>&1; then
        _pass "${image}_sh_is_dash_only"
    else
        _fail "${image}_sh_is_dash_only" "/bin/sh is missing or not dash"
    fi
done

echo ""
echo "==> Image contract results: ${PASS} passed, ${FAIL} failed"
if [[ ${FAIL} -gt 0 ]]; then
    echo "==> Failed contracts: ${FAILED_NAMES[*]}"
    exit 1
fi
