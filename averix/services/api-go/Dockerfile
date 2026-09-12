# The Go API.
#
# Two stages: a builder with the toolchain, and a runtime with nothing in it.
# The final image carries a static binary, the CA bundle and a non-root user —
# no shell, no package manager, nothing for an attacker who gets code
# execution to pick up and use.

FROM golang:1.25.0-alpine AS build

WORKDIR /src

# Dependencies first, so a change to the source does not re-download them.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

ARG VERSION=dev
# CGO off gives a static binary; trimpath and the empty build id keep the
# image reproducible and free of local paths.
RUN CGO_ENABLED=0 GOOS=linux go build \
      -trimpath \
      -ldflags="-s -w -buildid= -X github.com/averix/api/internal/app.Version=${VERSION}" \
      -o /out/averix-api ./cmd/api \
 && CGO_ENABLED=0 GOOS=linux go build \
      -trimpath -ldflags="-s -w -buildid=" \
      -o /out/averixctl ./cmd/averixctl \
 && CGO_ENABLED=0 GOOS=linux go build \
      -trimpath -ldflags="-s -w -buildid=" \
      -o /out/averix-worker ./cmd/worker

# The directory the filesystem storage driver writes into. It is created here
# so that the runtime image carries it owned by the unprivileged user: Docker
# seeds an empty named volume from the image path it is mounted over, taking
# its ownership with it. Without that, the volume arrives owned by root and a
# process running as uid 65532 cannot create a single file in it.
RUN mkdir -p /data/storage/private /data/storage/public

FROM gcr.io/distroless/static-debian12:nonroot AS runtime

COPY --from=build /out/averix-api /usr/local/bin/averix-api
COPY --from=build /out/averixctl /usr/local/bin/averixctl
COPY --from=build /out/averix-worker /usr/local/bin/averix-worker

# 65532 is distroless's "nonroot". Numeric because the image has no
# /etc/passwd lookup available to COPY at build time.
COPY --from=build --chown=65532:65532 /data /data

# Runs as uid 65532. Nothing in the image is writable by it, so a compromised
# process cannot modify the binary it is running.
USER nonroot:nonroot
WORKDIR /

EXPOSE 8080

# The health endpoint answers without touching the database, so this reports
# on the process rather than on its dependencies — readiness does that, and
# the orchestrator checks it separately.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/usr/local/bin/averixctl", "healthcheck"]

ENTRYPOINT ["/usr/local/bin/averix-api"]
