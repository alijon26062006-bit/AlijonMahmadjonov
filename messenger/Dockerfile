FROM node:22-alpine

WORKDIR /srv/aloqa
COPY server/package.json server/package-lock.json ./server/
RUN cd server && npm ci --omit=dev && npm cache clean --force
COPY server/server.js ./server/
COPY app ./app

ENV NODE_ENV=production PORT=8080 DATA_DIR=/data APP_DIR=/srv/aloqa/app
RUN mkdir -p /data && chown node:node /data
VOLUME /data
USER node
EXPOSE 8080
CMD ["node", "--disable-warning=ExperimentalWarning", "server/server.js"]
