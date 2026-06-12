# cyberware governance server (govd) — observe + govern; it NEVER executes.
# Pure-Python, stdlib only (no pip). The one addition is Java + the TLA+ tools so the COMPOSE step's
# deadlock check runs the real TLC model checker in-container, not just the structural fallback.
FROM python:3.11-slim

# Java (headless JRE) + tla2tools.jar — composer.run_tlc uses $TLA2TOOLS_JAR + `java` to model-check the
# blueprint for deadlock. Pinned version; bump TLA_VERSION to update. (~adds a JRE layer to the image.)
ARG TLA_VERSION=v1.8.0
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless ca-certificates curl \
 && curl -fsSL -o /opt/tla2tools.jar \
      "https://github.com/tlaplus/tlaplus/releases/download/${TLA_VERSION}/tla2tools.jar" \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV TLA2TOOLS_JAR=/opt/tla2tools.jar

WORKDIR /app

# the trusted registry + the infra — the server compiles/oversees from ITS OWN copy of these
COPY infra/ ./infra/
COPY skills/ ./skills/

# build-time authenticity gate: the image's copy of EVERY skill must match its committed index.json.
# This catches registry drift at build (e.g. a .dockerignore that strips a pinned file) — fail the build
# fast rather than ship a govd that would reject every claim. Exits 1 on any drift.
RUN python3 -m infra.tool.skill_index --check --all

ENV GOVD_CONFIG=/app/infra/govern/govd_config.json \
    GOVD_RECORD_ROOT=/data/govd \
    PYTHONUNBUFFERED=1

# the provenance ledger lives here — mount it to persist + review run records across restarts:
#   docker run -v cyberware-govd:/data/govd ...   (or  -v "$PWD/govd-ledger:/data/govd")
VOLUME ["/data/govd"]

# remote mode binds 0.0.0.0; map the port on `docker run`
EXPOSE 5773

HEALTHCHECK --interval=30s --timeout=3s --start-period=3s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5773/health').getcode()==200 else 1)"

CMD ["python3", "-m", "infra.govern.govd", "--mode", "remote", "--port", "5773"]
