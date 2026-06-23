# cyberware governance server (govd) — observe + govern; it NEVER executes.
# Mostly stdlib. Runtime deps: Java + the TLA+ tools (COMPOSE deadlock check via the real TLC), and
# `cryptography` — since P2-T12 govd's delegate import chain (infra.govern.delegate ->
# infra.exec.exodverify) needs Ed25519 at IMPORT time, so it's a hard dependency, not optional.
FROM python:3.11-slim

# Java (headless JRE) + tla2tools.jar — composer.run_tlc uses $TLA2TOOLS_JAR + `java` to model-check the
# blueprint for deadlock. Pinned version; bump TLA_VERSION to update. (~adds a JRE layer to the image.)
# git stays installed: CLOUD_MODE clones the skillChip live at boot (see the CMD below).
ARG TLA_VERSION=v1.8.0
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless ca-certificates curl git \
 && curl -fsSL -o /opt/tla2tools.jar \
      "https://github.com/tlaplus/tlaplus/releases/download/${TLA_VERSION}/tla2tools.jar" \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV TLA2TOOLS_JAR=/opt/tla2tools.jar

# cryptography: govd imports it transitively on startup (delegate -> exodverify, Ed25519 grants) since
# P2-T12. Pinned to the locked env (infra/pyenv/requirements.lock). manylinux wheel — no compiler needed.
RUN pip install --no-cache-dir cryptography==49.0.0

WORKDIR /app

# the engine + the baked cartridge — the server compiles/oversees from ITS OWN copy of these
COPY infra/ ./infra/
COPY skillChip/ ./skillChip/

# build-time authenticity gate: the image's copy of EVERY skill must match its committed index.json,
# and the chip manifest must match the skills. Catches registry drift at build (e.g. a .dockerignore
# stripping a pinned file) — fail the build fast rather than ship a govd that rejects every claim.
RUN python3 -m infra.tool.skill_index --check --all

# import smoke: govd's FULL startup import chain must load in-image (incl. cryptography via the delegate
# path). Fails the BUILD on a missing runtime dep instead of shipping a govd that crash-loops on a node
# (exactly the P2-T12 regression where the lean image lacked cryptography).
RUN python3 -c "import infra.govern.govd, infra.govern.delegate, infra.exec.exodverify; print('govd import chain OK')"

# non-root principal — govd/exod execute faithfully under a scoped service identity, NEVER root (the
# executor refuses uid 0). chown BEFORE the VOLUME line so a FRESH named volume inherits cyberware
# ownership (Docker seeds a new volume from the image path's content + perms); an existing root-owned
# volume must be re-chowned once (or use a fresh volume name).
RUN groupadd -g 1000 cyberware \
 && useradd -u 1000 -g cyberware -d /app -s /usr/sbin/nologin cyberware \
 && mkdir -p /data/govd \
 && chown -R cyberware:cyberware /app /data/govd

ENV GOVD_CONFIG=/app/infra/govern/govd_config.json \
    GOVD_RECORD_ROOT=/data/govd \
    PYTHONUNBUFFERED=1

# the provenance ledger lives here — mount it to persist + review run records across restarts:
#   docker run -v cyberware-govd:/data/govd ...   (or  -v "$PWD/govd-ledger:/data/govd")
VOLUME ["/data/govd"]

# remote mode binds 0.0.0.0; map the port on `docker run`
EXPOSE 5773

# drop to the non-root principal for runtime — every step the engine runs inherits this uid, never root
USER cyberware

# start-period covers a CLOUD_MODE clone+validate before the server binds
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5773/health').getcode()==200 else 1)"

# Boot = acquire + VALIDATE the chip, then exec govd pointed at it (chipfetch refuses to start on drift).
#   LOCAL (default): the baked chip above.
#   CLOUD:  docker run -e CLOUD_MODE=1 \
#             [-e CLOUD_SOURCE=https://github.com/rhCat/skillChip.git]   # the feed-stock repo (default)
#             [-e CLOUD_SOURCE_TAG=main]                                 # branch / tag / commit sha
#             [-e CLOUD_SOURCE_TOKEN=...]                                # private source (never logged/persisted)
CMD ["python3", "-m", "infra.govern.chipfetch", "--exec", \
     "python3", "-m", "infra.govern.govd", "--mode", "remote", "--port", "5773"]
