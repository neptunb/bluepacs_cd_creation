FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG BACKEND_INTERNAL_URL=http://cd-backend:8100
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}

# Subpath behind reverse proxy (e.g. /cd-yaz). Omit for root deployment.
ARG CD_BASE_PATH=
ENV CD_BASE_PATH=${CD_BASE_PATH}
# Client axios/download URLs must match server basePath; default NEXT_PUBLIC to CD_BASE_PATH.
ARG NEXT_PUBLIC_CD_BASE_PATH=
ENV NEXT_PUBLIC_CD_BASE_PATH=${NEXT_PUBLIC_CD_BASE_PATH:-$CD_BASE_PATH}

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3100

ENV PORT=3100
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
