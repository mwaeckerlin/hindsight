# Hindsight Docker Image

[mwaeckerlin/hindsight] runs [Hindsight], the agent memory server of vectorize.io, as one container: the API with one MCP endpoint per memory bank, the local embedding and reranking models, and the embedded PostgreSQL with pgvector. Agents such as Hermes, OpenClaw and OpenCode store and recall memories in it; a shared bank lets them share what they learned.

The models are part of the image, so the container downloads nothing when it starts and no text leaves the host to be embedded. The keys come as Docker secrets and never stand in the environment of the stack.

All features are listed in [FEATURES.md](FEATURES.md), all tests in [TESTS.md](TESTS.md).

The image is built on [mwaeckerlin/ubuntu-very-base] and ships on [mwaeckerlin/ubuntu-scratch]: PyTorch, which the local models need, exists for glibc only, so the Alpine bases of the family cannot carry it.

## Usage

```bash
$ printf '%s' "$TENANT_KEY" | docker secret create hindsight_tenant_key -
$ printf '%s' "$LITELLM_KEY" | docker secret create hindsight_llm_key -
$ printf '%s' "$CP_ACCESS_KEY" | docker secret create hindsight_cp_access_key -
```

With Docker Compose, [docker-compose.yml](docker-compose.yml) starts the API and the control plane with these secrets: `npm start`.

With a tenant key, every request to the API and to the MCP endpoints carries `Authorization: Bearer <tenant key>`; `/health` answers without a key.

- **API:** `http://<service>:8888/v1/default/banks/<bank>/memories` (retain) and `…/memories/recall` (recall)
- **MCP:** `http://<service>:8888/mcp/<bank>/`, one endpoint per memory bank
- **Health:** `http://<service>:8888/health`

### Control Plane

The second image `mwaeckerlin/hindsight:control-plane` is the web interface of Hindsight: on port 9999 an operator browses the memory banks, their memories, documents and entities, and runs recall and reflect by hand. It runs the control plane as upstream publishes it, on the headless [mwaeckerlin/nodejs], and carries no shell. [docker-compose.yml](docker-compose.yml) starts it beside the API.

| Variable | Default | Description |
| --- | --- | --- |
| `HINDSIGHT_CP_DATAPLANE_API_URL` | `http://hindsight:8888` | Address of the API |
| `HINDSIGHT_CP_DATAPLANE_API_KEY_FILE` | *(empty)* | File with the tenant key of the API, a Docker secret; needed when the API has one |
| `HINDSIGHT_CP_ACCESS_KEY_FILE` | *(empty)* | File with the access key of the login page, a Docker secret; without it the pages are open |

As with the API, the start reads every `HINDSIGHT_CP_*_FILE` into `HINDSIGHT_CP_*`, and a variable set both ways, a missing or an empty file stops the start with an error that names it.

## Administration

### Environment Variables

Every setting of Hindsight is an environment variable `HINDSIGHT_API_*`; the upstream [configuration reference] lists them. The ones a deployment sets:

| Variable | Default | Description |
| --- | --- | --- |
| `HINDSIGHT_API_LLM_PROVIDER` | *(upstream default)* | `openai` for any OpenAI-compatible server such as LiteLLM |
| `HINDSIGHT_API_LLM_BASE_URL` | *(upstream default)* | Address of that server, such as `http://litellm:4000/v1` |
| `HINDSIGHT_API_LLM_MODEL` | *(upstream default)* | Model name the server knows |
| `HINDSIGHT_API_LLM_API_KEY_FILE` | *(empty)* | File with the LLM key, a Docker secret |
| `HINDSIGHT_API_TENANT_API_KEY_FILE` | *(empty)* | File with the key every request must carry, a Docker secret; when it is set, the start switches the key check (`ApiKeyTenantExtension`) on, without it the API runs open |
| `HINDSIGHT_API_TENANT_EXTENSION` | *(set by the key)* | Another tenant extension of Hindsight, which then replaces the key check |
| `HINDSIGHT_API_WORKER_ID` | *(container host name)* | Stable name of this worker |
| `HINDSIGHT_API_PORT` | `8888` | Port of the API |

### Keys From Files

For every variable `HINDSIGHT_*_FILE`, the start reads the file and sets `HINDSIGHT_*` for Hindsight alone; the file variable itself is removed. A variable set both ways stops the start with an error that names it, and so does a file that is missing or empty.

### Volume

- `/data` — the embedded PostgreSQL with every memory bank. Persist it; it is the whole state of the service. On its first start PostgreSQL unpacks itself into this volume and creates the database, which takes a minute.

The container runs as `somebody` of [mwaeckerlin/ubuntu-scratch], uid 100, gid 1000, member of the group `shared-access` (gid 500); the volume must be writable for it. PostgreSQL needs about 30 seconds to write its checkpoint when the container stops, so give the service `stop_grace_period: 30s`.

## Security

- **No key in the environment:** keys reach the container as Docker secret files and are read by the start, so `docker inspect` and the stack file show a path, never a key. The end-to-end test checks the environment of the running container for the key.
- **Authentication on every request, optional:** with a tenant key, the API and every MCP endpoint refuse a request without the key or with a wrong one. Without a key the API runs open, and every client that reaches port 8888 reads and writes every memory bank. Run it without a key only where the network itself decides who reaches the service, such as a Swarm overlay network of its own, encrypted, that only the agents and their gateways join; everywhere else set the key.
- **Control plane login, optional:** with an access key, every page and every route of the control plane asks for it first. Whoever passes it reads and changes every memory bank with the tenant key of the control plane. Run it without an access key only behind a reverse proxy that asks for a login of its own, such as Traefik with Authentik, and never publish port 9999 directly.
- **One shell, for PostgreSQL:** the image carries no bash, busybox, perl or package manager. Its only shell is dash as `/bin/sh`, because the embedded PostgreSQL starts its own programs through it (`initdb`, `pg_ctl`); without it the service does not start. A PostgreSQL in a container of its own would need the same shell there, and would keep the API container free of it; the embedded one keeps the service in one container. For the same database the image carries `kill` and `ps`, with which pg0 checks and stops its server.
- **No download at runtime:** the models are baked in and `HF_HUB_OFFLINE` is set; the end-to-end test starts the service on a network without internet access.

## Development

```bash
$ npm test
```

`npm test` runs the docs contract, the unit tests of the start, the image contract, and the end-to-end test in [tests/e2e](tests/e2e): the image on a network without internet access with a mock LLM, retain and recall with the key, refusal without and with a wrong key, the MCP endpoint, the memory after a restart, the key missing from the container environment, and the control plane with and without its login. The image is published for `linux/amd64` and `linux/arm64` by the reusable workflow of [mwaeckerlin/scratch](https://github.com/mwaeckerlin/scratch#publishing-on-docker-hub).

## Licence

The MIT licence in [LICENSE](LICENSE) covers the files of this repository. Hindsight itself is MIT licensed as well; the models it ships keep their own licences (bge-small-en-v1.5 MIT, ms-marco-MiniLM-L-6-v2 Apache-2.0).

[mwaeckerlin/hindsight]: https://hub.docker.com/r/mwaeckerlin/hindsight "get the image from docker hub"
[Hindsight]: https://github.com/vectorize-io/hindsight
[configuration reference]: https://github.com/vectorize-io/hindsight/blob/main/hindsight-api-slim/hindsight_api/config.py
[mwaeckerlin/ubuntu-very-base]: https://github.com/mwaeckerlin/ubuntu-very-base
[mwaeckerlin/ubuntu-scratch]: https://github.com/mwaeckerlin/ubuntu-scratch
[mwaeckerlin/nodejs]: https://github.com/mwaeckerlin/nodejs
