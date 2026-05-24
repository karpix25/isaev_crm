# Build stage
FROM node:22-alpine AS build-stage

WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=4096

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run typecheck
RUN npm run build:vite

# Production stage
FROM nginx:stable-alpine AS production-stage

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
