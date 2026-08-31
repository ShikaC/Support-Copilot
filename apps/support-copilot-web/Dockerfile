FROM node:24-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS build

WORKDIR /app
COPY apps/support-copilot-web/package.json apps/support-copilot-web/package-lock.json ./
RUN npm ci

COPY apps/support-copilot-web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30.3-alpine-slim@sha256:3b24c4bfb2b9f60359b1475605ca1c8ed6e4963eb8369c6835be4d96bdb3ea81

USER root
RUN apk upgrade --no-cache
USER 101

COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/support-copilot-web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
