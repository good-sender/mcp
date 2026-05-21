# syntax=docker/dockerfile:1
# Builds the container image from binaries downloaded into ./bin/ by CI.

FROM alpine:3.21

ARG TARGETARCH

RUN apk add --no-cache ca-certificates wget \
	&& adduser -D -u 1000 goodsender

WORKDIR /data
RUN chown goodsender:goodsender /data

COPY bin/goodsender-mcp-linux-${TARGETARCH} /usr/local/bin/goodsender-mcp
RUN chmod +x /usr/local/bin/goodsender-mcp

USER goodsender

ENV GOODSENDER_HTTP_PORT=9889 \
	GOODSENDER_DB_FILE=/data/goodsender.sqlite \
	GOODSENDER_DATA_DIR=/data

EXPOSE 9889

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
	CMD wget -qO- http://127.0.0.1:9889/health || exit 1

ENTRYPOINT ["/usr/local/bin/goodsender-mcp"]
