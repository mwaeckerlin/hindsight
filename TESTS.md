# Tests

Register of all tests, sorted by the [FEATURES.md](FEATURES.md) number each test covers. `npm test` runs everything, locally and in the pipeline. The guard `tests/docs-contract.sh` fails when a feature has no test entry here or a test carries a skip marker.

## Unit

`npm run test:unit` runs `tests/unit` with the Python test runner and `control-plane/start.test.cjs` with the Node.js test runner.

- **F4** `tests/unit/test_start.py` › file becomes the variable, every hindsight file variable is read, foreign file variables stay untouched, both sources for one key stop the start, missing file stops the start and names it, empty file stops the start, empty file variable is ignored.
- **F9** `control-plane/start.test.cjs` › the keys of the control plane from `HINDSIGHT_CP_*_FILE`: a file becomes the variable, every file variable is read, foreign ones stay, both sources for one key stop the start, a missing and an empty file stop the start, an empty file variable is ignored.

## End-to-end

`npm run test:e2e` starts the built images in `tests/e2e/docker-compose.yml` on a network without internet access, with a mock LLM and the tenant key and the access key of the control plane as Docker secrets, and runs `tests/e2e/check_hindsight.py` in a client container.

- **F1** `tests/e2e/check_hindsight.py` › retain_with_key, recall_with_key_finds_the_fact, mcp_endpoint_answers_with_key.
- **F2** `tests/e2e/check_hindsight.py` › memory_survives_a_restart, after `docker compose restart` of the service.
- **F3** `tests/run-e2e.sh` › hindsight_becomes_healthy_without_internet.
- **F4** `tests/run-e2e.sh` › tenant_key_not_in_environment.
- **F5** `tests/e2e/check_hindsight.py` › health_answers_without_key, api_refuses_request_without_key, api_refuses_wrong_key, mcp_endpoint_refuses_without_key, and on a second service without a key: without_tenant_key_the_api_runs_open.
- **F5** `tests/unit/test_start.py` › a tenant key switches the key check on, without a tenant key the service runs open, an extension set by the operator stays.
- **F6** `tests/run-e2e.sh` › the service reaches the state `healthy` through its own health check, before and after the restart.
- **F9** `tests/e2e/check_hindsight.py` › control_plane_sends_to_login_without_session, control_plane_api_refuses_without_session, control_plane_refuses_wrong_access_key, control_plane_login_with_access_key, control_plane_lists_the_banks_with_the_tenant_key, control_plane_page_renders_after_login: the control plane in front of the service with the key, with its access key as a Docker secret.
- **F9** `tests/e2e/check_hindsight.py` › control_plane_without_access_key_runs_open, control_plane_open_lists_the_banks: the control plane without an access key, in front of the service without a key.
- **F9** `tests/run-e2e.sh` › both control plane containers reach the state `healthy` through their own health check.
## Image contract

- **F7** `tests/image-contract.sh` › no bash in `/bin` or `/usr/bin`, no busybox, no perl, no apt-get, and `/bin/sh` is dash and nothing else.
- **F9** `tests/image-contract.sh` › the control plane image `mwaeckerlin/hindsight:control-plane` carries none of these tools and no `/bin/sh` at all.

## Workflow contract

- **F8** `tests/workflow-contract.sh` of `mwaeckerlin/scratch` — the reusable workflow selects exactly the images a repository publishes; this repository calls it from `.github/workflows/docker.yml`.
