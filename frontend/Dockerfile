# Causality frontend — Vite dev server (React + TS).
# Dev mode keeps the origin on :5173, which the backend's CORS allow-lists, and
# sidesteps the not-yet-verified production build.
FROM node:20-slim

WORKDIR /app

# Install deps first so the layer caches across source edits.
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host 0.0.0.0 so Vite is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
