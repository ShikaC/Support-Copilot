FROM eclipse-temurin:21-jdk-jammy@sha256:ce5767b7222312d42395f5bab033cd91f09e44032a2f21bdfd7b5b912dbe1e77 AS build

WORKDIR /workspace

COPY services/support-copilot-api/ services/support-copilot-api/
COPY services/support-copilot-ai/app/data/knowledge.json services/support-copilot-ai/app/data/knowledge.json

WORKDIR /workspace/services/support-copilot-api
RUN ./gradlew bootJar --no-daemon --no-watch-fs

FROM eclipse-temurin:21-jre-jammy@sha256:eebd356ad7358b7094758e5787a6726f332917cfd56feab6457c56dab895cdbf

RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 appuser

WORKDIR /opt/support-copilot
COPY --from=build /workspace/services/support-copilot-api/build/libs/support-copilot-api-0.0.1-SNAPSHOT.jar app.jar
COPY --from=build --chown=10001:10001 /workspace/services/support-copilot-ai/app/data/knowledge.json knowledge/knowledge.json

ENV SUPPORT_COPILOT_KNOWLEDGE_CORPUS_PATH=/opt/support-copilot/knowledge/knowledge.json

USER 10001
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/opt/support-copilot/app.jar"]
