# Local-development image only. It retains the pinned official MinIO server and adds BusyBox wget
# solely so Compose can call MinIO's documented HTTP health endpoint from the container health check.
FROM minio/minio:RELEASE.2025-04-22T22-12-26Z

COPY --from=busybox:1.37.0-musl /bin/busybox /usr/local/bin/busybox
RUN ln -s /usr/local/bin/busybox /usr/local/bin/wget
