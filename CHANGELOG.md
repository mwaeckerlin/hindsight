# Changelog

- 2026-09-29 **1.0.0**
    - Hindsight, the agent memory server, as one container without bash, busybox, perl or package manager: the API with one MCP endpoint per memory bank, the local models and the embedded PostgreSQL
    - The key every request must carry is optional: with it the API and the MCP endpoints refuse every request without it, without it they run open
    - The models are part of the image, so the service starts and works without internet access
    - Keys come as Docker secrets and never stand in the environment of the container
    - Published for amd64 and arm64 under one tag, built, tested and published automatically on every change and every week
