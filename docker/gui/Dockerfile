FROM node:20-alpine
WORKDIR /app
COPY apps/agui/package.json ./
COPY apps/agui/package-lock.json ./
# Use legacy peer deps to handle React version conflicts
RUN npm ci --legacy-peer-deps
RUN npm install --save-dev @types/js-cookie --legacy-peer-deps
COPY apps/agui ./
RUN npm run build
CMD ["npm", "run", "start"]
