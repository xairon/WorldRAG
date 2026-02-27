FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./

# ── Dev target (hot-reload via volume mount) ─────────────────────────
FROM base AS dev
RUN npm ci
# Source mounted as volume in docker-compose — don't COPY
CMD ["npx", "next", "dev", "--hostname", "0.0.0.0"]

# ── Builder (production) ─────────────────────────────────────────────
FROM base AS builder
RUN npm ci
COPY . .
RUN npm run build

# ── Prod target ──────────────────────────────────────────────────────
FROM node:22-alpine AS prod
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
