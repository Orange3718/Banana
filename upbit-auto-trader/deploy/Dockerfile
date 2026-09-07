FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY apps/dashboard/package*.json ./
RUN npm ci
COPY apps/dashboard/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY next_requirements.txt ./
RUN pip install --no-cache-dir -r next_requirements.txt
COPY neural ./neural
COPY --from=frontend /build/dist ./apps/dashboard/dist
RUN useradd --uid 10001 --create-home neural && mkdir /data && chown neural /data
USER neural
ENV NEURAL_DATA_DIR=/data
EXPOSE 8765
CMD ["uvicorn", "neural.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
