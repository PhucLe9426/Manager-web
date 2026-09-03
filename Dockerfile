# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN --mount=type=cache,target=/root/.npm \
    npm install \
      --registry=$NPM_REGISTRY \
      --no-audit \
      --no-fund \
      --prefer-offline \
      --fetch-retries=2 \
      --fetch-retry-mintimeout=5000 \
      --fetch-retry-maxtimeout=30000 \
      --fetch-timeout=60000 \
      --loglevel=verbose

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/scripts ./scripts
COPY --from=deps --chown=nextjs:nodejs /app/node_modules/postgres ./node_modules/postgres
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
