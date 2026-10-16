# Two targets: `dev` (Vite dev server, hot reload; what compose.yaml runs) and
# `prod` (static build served by nginx; ~10 MB of RAM instead of ~800 MB).

FROM node:22-alpine AS dev

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


FROM dev AS build

# .env.local is excluded from the build context (.dockerignore), so the
# browser-side settings arrive as build args; Vite reads VITE_* from the
# environment. VITE_API_URL stays same-origin: nginx below proxies /api.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
ARG VITE_API_URL=/api/v1
RUN test -n "$VITE_SUPABASE_URL" && test -n "$VITE_SUPABASE_PUBLISHABLE_KEY" \
    || { echo "Set the VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY build args" >&2; exit 1; }
RUN npm run build


FROM nginxinc/nginx-unprivileged:stable-alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Same port as the dev server, so proxies in front need no change.
EXPOSE 5173
