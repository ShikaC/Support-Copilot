FROM mysql:8.4.11-oraclelinux9@sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb

ARG CURL_VERSION=7.76.1-40.el9_8.5
ARG SQLITE_LIBS_VERSION=3.34.1-11.el9_8

RUN microdnf install --assumeyes \
        "curl-${CURL_VERSION}" \
        "libcurl-${CURL_VERSION}" \
        "sqlite-libs-${SQLITE_LIBS_VERSION}" \
        util-linux-core \
    && microdnf remove --assumeyes mysql-shell \
    && microdnf clean all \
    && test "$(rpm --query --queryformat '%{VERSION}-%{RELEASE}' curl)" = "${CURL_VERSION}" \
    && test "$(rpm --query --queryformat '%{VERSION}-%{RELEASE}' libcurl)" = "${CURL_VERSION}" \
    && test "$(rpm --query --queryformat '%{VERSION}-%{RELEASE}' sqlite-libs)" = "${SQLITE_LIBS_VERSION}" \
    && ! rpm --query mysql-shell \
    && command -v setpriv >/dev/null \
    && rpm --query --whatprovides "$(command -v setpriv)"

COPY --chmod=0755 infra/images/mysql/gosu /usr/local/bin/gosu

RUN test "$(od -An -tx1 -N4 /usr/local/bin/gosu | tr -d ' ')" != 7f454c46 \
    && grep -Fqx '#!/bin/sh' /usr/local/bin/gosu
