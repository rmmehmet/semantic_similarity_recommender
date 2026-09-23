FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Same-origin relative path — nginx reverse-proxies /api to the backend
# on this same domain. Do NOT set an absolute cross-origin URL here;
# the backend's session cookie is samesite=lax with no domain set, so
# frontend and backend must share an origin or login silently breaks.
ENV VITE_API_URL=/api
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
