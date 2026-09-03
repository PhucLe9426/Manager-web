FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund

COPY worker.mjs ./

CMD ["npm", "start"]

