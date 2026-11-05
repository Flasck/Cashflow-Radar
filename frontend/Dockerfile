FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

ENV RADAR_API_URL=http://api:8000 NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1 RADAR_API_URL=http://api:8000

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

USER node

EXPOSE 3000

CMD ["node", "server.js"]
