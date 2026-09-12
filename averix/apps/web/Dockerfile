# The web application.
#
# Next.js standalone output: the runtime image carries the server, the built
# pages and only the dependencies they actually import.

FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

RUN addgroup --system --gid 10002 averix \
 && adduser --system --uid 10002 --ingroup averix averix

# The standalone bundle, then the assets it serves.
COPY --from=build --chown=averix:averix /app/.next/standalone ./
COPY --from=build --chown=averix:averix /app/.next/static ./.next/static
COPY --from=build --chown=averix:averix /app/public ./public

USER averix
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
