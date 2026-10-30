# syntax=docker/dockerfile:1

FROM node:20-alpine AS build

WORKDIR /app
ENV CI=true

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Types and tests gate the image: a frontend that does not typecheck never ships.
RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/firewatch.conf

# The bundle is static; the API is proxied at /api so no secrets or origins are
# baked into the browser build.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
