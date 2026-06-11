#!/usr/bin/env bash
# docker_build — build an image from a context dir (proven pathway). Structured JSON output.
set -uo pipefail
: "${CONTEXT_DIR:?}" "${IMAGE_TAG:?}" "${RECORD_STORE:?}"
LOG="${RECORD_STORE%/}/docker_build.log"
docker build -t "$IMAGE_TAG" ${DOCKERFILE:+-f "$DOCKERFILE"} "$CONTEXT_DIR" > "$LOG" 2>&1
RC=$?
printf '{"tool":"docker_build","status":"%s","image":"%s","exit":%d,"log":"%s"}\n' "$([ $RC -eq 0 ] && echo ok || echo fail)" "$IMAGE_TAG" "$RC" "$LOG"
exit $RC
