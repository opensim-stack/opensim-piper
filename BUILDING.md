# Building

Build and publish a multiarch image.

## Local Build

```bash
docker build -t opensim-piper:local .
```

### Run Local

```bash
docker run --rm \
  -e PIPER_HTTP_HOST=0.0.0.0 \
  -e PIPER_HTTP_PORT=8995 \
  -e PIPER_DEFAULT_VOICE=en_US-lessac-medium \
  -p 8995:8995 \
  -v piper-voices:/voices \
  opensim-piper:local
```

## Publish

### Setup

Create/use a buildx builder once:

```bash
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap
```

### Build

Build and push Linux AMD64 + ARM64:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t bithatch/opensim-piper:latest \
  -t bithatch/opensim-piper:$(date +%Y%m%d) \
  --push \
  .
```

## Automated Publish (GitHub Actions)

This repository includes `.github/workflows/docker-publish.yml` to automatically build and push a multiarch image to Docker Hub.

### Triggers

- Pushes to `master` or `main` when `Dockerfile`, `docker/**`, or the workflow itself changes
- Git tags matching `v*`
- Manual `workflow_dispatch`

### Required Repository Secrets

- `DOCKERHUB_USERNAME`: Docker Hub username or org robot account name
- `DOCKERHUB_TOKEN`: Docker Hub access token (recommended) or password

### Published Platforms and Tags

- Platforms: `linux/amd64`, `linux/arm64`
- Tags (default branch): `latest`, `YYYYMMDD`, and `sha-<commit>`
- Tags (tag builds): `<git-tag>` and `sha-<commit>`
