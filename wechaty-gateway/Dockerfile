FROM node:20-alpine

WORKDIR /app

# Install deps first for layer caching. Wechaty is an optionalDependency, so a
# mock-mode image still builds if the registry is unavailable.
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund || true

COPY src ./src

ENV NODE_ENV=production \
    WECHATY_GATEWAY_MODE=mock \
    WECHATY_GATEWAY_PORT=8788

EXPOSE 8788

CMD ["node", "src/server.mjs"]
