FROM node:22 AS build

WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm ci --registry=$NPM_REGISTRY

COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
