#!/usr/bin/env python3
"""Start the Hindsight API with its secrets read from files.

Hindsight reads every setting from a HINDSIGHT_API_* environment variable,
keys included. A key in the environment of a stack file is readable by anyone
who can inspect the service, so the image takes the keys as Docker secrets:
for every variable NAME_FILE that is set, the content of that file becomes
NAME, and NAME_FILE is removed. Then the process becomes hindsight-api, with
no shell in between.

    HINDSIGHT_API_LLM_API_KEY_FILE=/run/secrets/litellm_key
    HINDSIGHT_API_TENANT_API_KEY_FILE=/run/secrets/hindsight_tenant_key

A NAME that is set as well as NAME_FILE stops the start: two sources for one
key leave it open which one is in use.

    start.py            start the API
    start.py --health   exit 0 when the API answers /health, for HEALTHCHECK
"""
import os
import sys

SUFFIX = "_FILE"
PREFIX = "HINDSIGHT_"
TENANT_EXTENSION = "hindsight_api.extensions.builtin.tenant:ApiKeyTenantExtension"


def secrets_from_files(environment):
    """Replace every HINDSIGHT_*_FILE by the content of its file."""
    for name in sorted(key for key in environment if key.startswith(PREFIX) and key.endswith(SUFFIX)):
        target = name[: -len(SUFFIX)]
        path = environment.pop(name)
        if not path:
            continue
        if environment.get(target):
            raise SystemExit(f"start: {target} and {name} are both set; set one of them")
        try:
            with open(path, encoding="utf-8") as handle:
                value = handle.read().strip()
        except OSError as error:
            raise SystemExit(f"start: {name} names {path}, which cannot be read: {error.strerror}")
        if not value:
            raise SystemExit(f"start: {name} names {path}, which is empty")
        environment[target] = value
    return environment


def tenant_key_check(environment):
    """A tenant key switches the key check on; without one the API runs open.

    The key is optional because a deployment may isolate the service on a
    network of its own instead. An extension the operator named stays.
    """
    if environment.get("HINDSIGHT_API_TENANT_API_KEY") and not environment.get("HINDSIGHT_API_TENANT_EXTENSION"):
        environment["HINDSIGHT_API_TENANT_EXTENSION"] = TENANT_EXTENSION
    return environment


def health():
    """Exit 0 when the API answers its health endpoint."""
    from hindsight_api.http_probe import probe

    port = os.environ.get("HINDSIGHT_API_PORT", "8888")
    return 0 if probe(f"http://127.0.0.1:{port}/health", 5) else 1


def main():
    if sys.argv[1:] == ["--health"]:
        return health()
    environment = tenant_key_check(secrets_from_files(dict(os.environ)))
    program = os.path.join(os.environ.get("VIRTUAL_ENV", "/opt/hindsight/venv"), "bin", "hindsight-api")
    os.execve(program, [program, *sys.argv[1:]], environment)


if __name__ == "__main__":
    sys.exit(main())
