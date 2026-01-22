FROM python:3.12 as builder
COPY . .
RUN pip install --upgrade build
RUN python -m build

FROM python:3.12-alpine

# Create non-root user for security
RUN addgroup -g 1000 exporter && \
    adduser -u 1000 -G exporter -s /bin/sh -D exporter

COPY --from=builder /dist/* dist/
RUN pip install dist/*-py2.py3-none-any.whl && \
    rm -rf dist/

# Switch to non-root user
USER exporter

# Expose the default port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["salesforce-exporter", "start-server"]
