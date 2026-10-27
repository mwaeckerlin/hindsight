# Ubuntu and not the Alpine very-base: PyTorch, which the local embedding and
# reranking models need, exists for glibc only, so the build stage is
# mwaeckerlin/ubuntu-very-base and the final stages mwaeckerlin/ubuntu-scratch.

ARG HINDSIGHT_REPOSITORY="vectorize-io/hindsight"

#### build: the upstream source and its Python environment ####
FROM mwaeckerlin/ubuntu-very-base AS build
RUN apt-get update && $PKG_INSTALL ca-certificates curl git python3 build-essential tzdata procps
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
ENV UV_PYTHON_INSTALL_DIR="/opt/hindsight/python" \
    UV_CACHE_DIR="/root/.cache/uv" \
    UV_PROJECT_ENVIRONMENT="/opt/hindsight/venv" \
    VIRTUAL_ENV="/opt/hindsight/venv" \
    UV_LINK_MODE="copy" \
    UV_COMPILE_BYTECODE="1" \
    UV_PYTHON_PREFERENCE="only-managed" \
    UV_HTTP_TIMEOUT="600" \
    UV_HTTP_RETRIES="10" \
    HF_HOME="/opt/hindsight/models"
# The upstream source, main branch by default, as the archive of that branch:
# a git fetch of the whole repository broke off after an hour on a slow link,
# the archive is one download that is repeated when it breaks. ADD of the
# commit feed of the branch is compared on every build, so a new upstream
# commit rebuilds from here; the feed changes with a commit only, and unlike
# the GitHub API, which answered a shared runner with 403, it has no limit
# for requests without a token.
ARG HINDSIGHT_REPOSITORY
ARG HINDSIGHT_BRANCH="main"
ADD https://github.com/${HINDSIGHT_REPOSITORY}/commits/${HINDSIGHT_BRANCH}.atom /opt/hindsight/upstream-commits.atom
RUN install -d /opt/hindsight/src \
    && curl -fL --retry 10 --retry-all-errors --retry-delay 10 --connect-timeout 30 \
         -o /tmp/hindsight.tar.gz "https://github.com/${HINDSIGHT_REPOSITORY}/archive/refs/heads/${HINDSIGHT_BRANCH}.tar.gz" \
    && tar -xzf /tmp/hindsight.tar.gz --strip-components=1 -C /opt/hindsight/src \
    && rm /tmp/hindsight.tar.gz
WORKDIR /opt/hindsight/src
# The API with the local models and the embedded PostgreSQL, from upstream's
# lock file, installed into the environment and not linked to the source.
RUN --mount=type=cache,id=/home/somebody/.cache/uv,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev --package hindsight-api-slim --extra local-ml --extra embedded-db
# The models are part of the image: the container downloads nothing when it
# starts, and no text leaves the host to be embedded. The two public models
# need no token; without one the Hub prints a warning about rate limits,
# which the build does not want as output, and a token has no place in the
# image.
RUN HF_HUB_VERBOSITY=error HF_HUB_DISABLE_PROGRESS_BARS=1 /opt/hindsight/venv/bin/python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
COPY bin /opt/hindsight/bin
RUN /opt/hindsight/venv/bin/python -m compileall -q /opt/hindsight/bin
# pg0 unpacks PostgreSQL only when it starts, so the build starts and stops it
# once, as the unprivileged build user PostgreSQL demands, and the runtime
# closure below reads the shared libraries of the unpacked binaries; a
# library found missing at runtime (liblzma, measured 2026-09-28) is found here.
RUN install -d -o ${BUILD_USER} /tmp/pg0-home \
    && runuser -u ${BUILD_USER} -- env HOME=/tmp/pg0-home /opt/hindsight/venv/bin/python -c "\
from pg0 import Pg0; \
database = Pg0(name='build'); \
database.start(); \
database.stop()"
# The runtime closure: the shared libraries of every binary in /opt/hindsight
# and of the PostgreSQL unpacked above. pg0 checks and stops its server with
# external commands: the version upstream locks (0.15.0) runs `kill -0 <pid>`
# and `kill`, later versions `ps -p <pid> -o comm=`. Without them it reports no
# connection address and the API cannot start (measured 2026-09-29), so both
# are part of the runtime.
RUN python3 /opt/hindsight/bin/collect-runtime.py /runtime \
      --scan /opt/hindsight /tmp/pg0-home/.pg0/installation \
      --files /etc/ssl/certs /usr/share/ca-certificates /usr/share/zoneinfo /usr/lib/locale/C.utf8 /usr/bin/ps /usr/bin/kill \
      --packages 'libssl3*' 'libgssapi-krb5-2*' 'libkrb5*' 'libk5crypto3*' 'libkrb5support0*' \
                 'libcom-err2*' 'libkeyutils1*' 'liblz4-1*' 'libreadline8*' 'libncursesw6*' 'libtinfo6*' 'libzstd1*'
# The one exception to the headless image: the embedded PostgreSQL runs its
# own programs through /bin/sh (initdb calls `postgres -V`, pg_ctl starts the
# server with `sh -c exec postgres`), measured on 2026-09-28 when the start
# failed without it. So the image carries dash as /bin/sh and nothing more:
# no bash, no busybox, no perl, no package manager.
RUN install -D -m 755 /usr/bin/dash /runtime/usr/bin/dash \
    && ln -sf dash /runtime/usr/bin/sh \
    && if [ ! -e /runtime/bin ]; then ln -s usr/bin /runtime/bin; fi \
    && test "$(readlink -f /runtime/bin)" = /runtime/usr/bin
RUN install -d -m 1777 /runtime/tmp
RUN install -d /volumes/data

#### the API: no shell, no package manager ####
FROM mwaeckerlin/ubuntu-scratch AS api
# initdb refuses a locale without its data (measured 2026-09-28 with the
# en_US.UTF-8 of the base); C.UTF-8 ships with the C library and is collected
# above.
ENV CONTAINERNAME="hindsight" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    TZ="UTC" \
    PATH="/opt/hindsight/venv/bin:/usr/bin" \
    VIRTUAL_ENV="/opt/hindsight/venv" \
    HOME="/data" \
    HF_HOME="/opt/hindsight/models" \
    HF_HUB_OFFLINE="1" \
    TRANSFORMERS_OFFLINE="1" \
    HF_HUB_DISABLE_TELEMETRY="1" \
    TRANSFORMERS_VERBOSITY="error" \
    HF_HUB_VERBOSITY="error" \
    TOKENIZERS_PARALLELISM="false" \
    PYTHONUNBUFFERED="1" \
    PYTHONUTF8="1" \
    HINDSIGHT_API_HOST="0.0.0.0" \
    HINDSIGHT_API_PORT="8888" \
    HINDSIGHT_API_LOG_LEVEL="info"
EXPOSE 8888
VOLUME ["/data"]
# The first start unpacks PostgreSQL and loads the models; later starts are
# faster.
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD ["/opt/hindsight/venv/bin/python", "/opt/hindsight/bin/start.py", "--health"]
WORKDIR /data
ENTRYPOINT ["/opt/hindsight/venv/bin/python", "/opt/hindsight/bin/start.py"]
COPY --from=build /runtime/ /
COPY --from=build --chown=0:0 /opt/hindsight/python /opt/hindsight/python
COPY --from=build --chown=0:0 /opt/hindsight/venv /opt/hindsight/venv
COPY --from=build --chown=0:0 /opt/hindsight/models /opt/hindsight/models
COPY --from=build --chown=0:0 /opt/hindsight/bin /opt/hindsight/bin
COPY --from=build --chown=${RUN_USER}:${RUN_GROUP} /volumes/ /

#### control-plane-build: the web interface as upstream publishes it ####
# The npm package carries the built Next.js standalone server with its own
# node_modules, so nothing is compiled here. It unpacks to 75MB: on a slow
# link the default read timeout broke the download off after 28 minutes
# (measured 2026-09-29), so the download waits longer and repeats.
FROM mwaeckerlin/nodejs-build AS control-plane-build
RUN --mount=type=cache,target=/home/coder/.npm,uid=101,gid=1001 \
    npm install --omit=dev --ignore-scripts --no-save \
      --fetch-timeout=1800000 --fetch-retries=10 --fetch-retry-mintimeout=10000 \
      @vectorize-io/hindsight-control-plane@latest \
    && test -f node_modules/@vectorize-io/hindsight-control-plane/standalone/server.js

#### control-plane-base-path-build: the same release below a base path ####
# Next.js builds its base path into the pages and bundles, so the base path
# is a build of its own: upstream's next.config.ts takes it from
# NEXT_PUBLIC_BASE_PATH as basePath and assetPrefix. The source is the release
# tag of the npm package installed above, so both builds are the same version;
# a stage of its own, so no module of that package is found from the source.
FROM mwaeckerlin/nodejs-build AS control-plane-base-path-build
ARG HINDSIGHT_REPOSITORY
COPY --from=control-plane-build /app/node_modules/@vectorize-io/hindsight-control-plane/package.json /tmp/release.json
RUN version="$(node -p "require('/tmp/release.json').version")" \
    && curl -fL --retry 10 --retry-all-errors --retry-delay 10 --connect-timeout 30 \
         -o /tmp/hindsight.tar.gz "https://github.com/${HINDSIGHT_REPOSITORY}/archive/refs/tags/v${version}.tar.gz" \
    && mkdir /tmp/hindsight \
    && tar -xzf /tmp/hindsight.tar.gz -C /tmp/hindsight \
    && mv /tmp/hindsight/* /app/upstream \
    && rm -r /tmp/hindsight /tmp/hindsight.tar.gz
WORKDIR /app/upstream
# The versions of upstream's lock file, which carries the native bindings for
# musl on amd64 and arm64; the TypeScript client is built first, the control
# plane imports it.
RUN --mount=type=cache,target=/home/coder/.npm,uid=101,gid=1001 \
    npm ci --ignore-scripts \
      --fetch-timeout=1800000 --fetch-retries=10 --fetch-retry-mintimeout=10000 \
      -w @vectorize-io/hindsight-client -w @vectorize-io/hindsight-control-plane
RUN npm run build -w @vectorize-io/hindsight-client
COPY control-plane/start.cjs control-plane/prepare-base-path.cjs /app/prepare/
ARG HINDSIGHT_BASE_PATH="/hindsight"
RUN node /app/prepare/prepare-base-path.cjs hindsight-control-plane "${HINDSIGHT_BASE_PATH}"
WORKDIR /app/upstream/hindsight-control-plane
RUN NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_BASE_PATH="${HINDSIGHT_BASE_PATH}" npm exec -- next build
# upstream's own script that lays out the standalone directory of the npm package
RUN npm run build:standalone
RUN test "$(node -p "require('/app/prepare/start.cjs').builtBasePath('standalone')")" = "${HINDSIGHT_BASE_PATH}"

#### control-plane: browse the memory banks, on the headless Node.js base ####
FROM mwaeckerlin/nodejs AS control-plane
ENV CONTAINERNAME="hindsight-control-plane" \
    NODE_ENV="production" \
    HOSTNAME="0.0.0.0" \
    PORT="9999" \
    NEXT_TELEMETRY_DISABLED="1" \
    HINDSIGHT_CP_DATAPLANE_API_URL="http://hindsight:8888"
EXPOSE 9999
COPY --from=control-plane-build /app/node_modules/@vectorize-io/hindsight-control-plane/standalone /app/control-plane
COPY --from=control-plane-base-path-build /app/upstream/hindsight-control-plane/standalone /app/control-plane-base-path
COPY control-plane/start.cjs /app/start.cjs
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["/usr/bin/node", "/app/start.cjs", "--health"]
CMD ["/app/start.cjs"]

FROM api
