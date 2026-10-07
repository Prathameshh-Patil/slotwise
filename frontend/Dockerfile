# Development image: runs `next dev` with your code mounted in by Docker Compose.
FROM node:24-alpine

WORKDIR /app

# Install dependencies first, in their own cached layer (same idea as the API image)
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
