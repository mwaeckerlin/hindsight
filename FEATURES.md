# Features

Numbered register of every feature; a number is never reused. Every feature is covered by tests listed in [TESTS.md](TESTS.md); the guard `tests/docs-contract.sh` fails when a feature has no test.

- **F1 — Memory API and MCP endpoints.** Agents retain and recall memories through the API on port 8888, and reach every memory bank as an MCP server at `/mcp/<bank>/`.
- **F2 — Everything in one container.** The embedded PostgreSQL with pgvector runs inside the service; all state lies in the volume `/data` and survives a restart.
- **F3 — No download at runtime.** The embedding and reranking models are part of the image; the service starts and embeds on a network without internet access.
- **F4 — Keys from Docker secrets.** Every `HINDSIGHT_*_FILE` becomes the variable `HINDSIGHT_*` for Hindsight alone; a key never stands in the environment of the container, and a missing, empty or doubly set key stops the start with a message that names it.
- **F5 — An optional key on every request.** With a tenant key, the API and the MCP endpoints refuse a request without the key or with a wrong one; without a key the API runs open, for a network that decides itself who reaches it. `/health` stays open.
- **F6 — Health check.** The image checks `/health` itself, so Docker and the stack see when the service is ready.
- **F7 — No tool to pivot with.** The image contains no bash, no busybox, no perl and no package manager; its only shell is dash as `/bin/sh`, which the embedded PostgreSQL needs to run its own programs.
- **F8 — Published for amd64 and arm64.** Every push builds the image natively for both architectures and publishes it under one tag on Docker Hub, with the reusable workflow of `mwaeckerlin/scratch`.
