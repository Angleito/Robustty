FROM node:20-alpine

# Install build dependencies and curl for health checks
RUN apk add --no-cache python3 make g++ ffmpeg curl opus-dev libsodium-dev

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build TypeScript with increased memory
RUN NODE_OPTIONS="--max-old-space-size=2048" npm run build

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nodejs -u 1001

# Change ownership
RUN chown -R nodejs:nodejs /app

USER nodejs

# Start the bot
CMD ["node", "dist/index.js"]