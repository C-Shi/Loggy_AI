FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY . .
RUN npm install
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

ENV NODE_ENV=production
ENV PORT=8080

CMD ["node", "server/index.js"]