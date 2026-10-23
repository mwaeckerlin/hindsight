# Changelog

- 2026-10-23 **1.0.3**
    - The build reads the current package lists before it installs, as `mwaeckerlin/ubuntu-very-base` asks; with the lists of the base image's last weekly build, apt asked for a `ca-certificates` the Ubuntu mirror no longer had and the arm64 build failed

- 2026-10-23 **1.0.2**
    - The weekly rebuild starts at 07:17 on Monday, after `mwaeckerlin/nodejs-build` of 06:17 that this image is built on; at 05:17 it took the build of the week before

- 2026-09-29 **1.0.1**
    - The control plane, the web interface for browsing the memory banks, as the second image `mwaeckerlin/hindsight:control-plane` on port 9999, without a shell; its keys come as Docker secrets, and its login is optional

- 2026-09-29 **1.0.0**
    - Hindsight, the agent memory server, as one container without bash, busybox, perl or package manager: the API with one MCP endpoint per memory bank, the local models and the embedded PostgreSQL
    - The key every request must carry is optional: with it the API and the MCP endpoints refuse every request without it, without it they run open
    - The models are part of the image, so the service starts and works without internet access
    - Keys come as Docker secrets and never stand in the environment of the container
    - Published for amd64 and arm64 under one tag, built, tested and published automatically on every change and every week
