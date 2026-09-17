FROM ghcr.io/navikt/mock-oauth2-server:6.0.2@sha256:b538810afd589d42fbfb856c588c2065eaeed1dc528d6c532972048e67fc2aff AS upstream

FROM cgr.dev/chainguard/jre@sha256:dbe71fe6d7de0b29342cd3dd693e713098088ddc3d2be904a721ffea905e1569

LABEL org.opencontainers.image.title="Support Copilot test-only OIDC issuer"
LABEL org.opencontainers.image.source="https://github.com/navikt/mock-oauth2-server"
LABEL org.opencontainers.image.revision="118597560f2a3cff0aad51e17d2511c8cb4221b9"
LABEL org.opencontainers.image.base.name="cgr.dev/chainguard/jre@sha256:dbe71fe6d7de0b29342cd3dd693e713098088ddc3d2be904a721ffea905e1569"
LABEL io.support-copilot.test-only="true"
LABEL io.support-copilot.oidc.upstream="ghcr.io/navikt/mock-oauth2-server:6.0.2@sha256:b538810afd589d42fbfb856c588c2065eaeed1dc528d6c532972048e67fc2aff"
LABEL io.support-copilot.oidc.provenance="linux/amd64-app-manifest:sha256:8734e6a7c258ee928fb18ad64c2d55fe3f9488b735587d489661e89c0b9bf2c2"

COPY --from=upstream --chown=65532:65532 /app /app

USER 65532
WORKDIR /app
EXPOSE 8080
ENTRYPOINT ["java", "--sun-misc-unsafe-memory-access=allow", "-cp", "@/app/jib-classpath-file", "no.nav.security.mock.oauth2.StandaloneMockOAuth2ServerKt"]
