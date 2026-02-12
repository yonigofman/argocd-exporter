# ArgoCD Exporter for Grafana Alloy

A lightweight Prometheus exporter written in Python to monitor multiple ArgoCD servers. This exporter is specifically designed to work seamlessly with Grafana Alloy or any Prometheus-compatible monitoring system.

## Features

- **Multi-Server Support**: Monitor multiple ArgoCD instances simultaneously.
- **Asynchronous API Calls**: Uses `httpx` for efficient, non-blocking API requests.
- **Prometheus Metrics**: Exposes application health, sync status, and server availability.
- **Customizable**: Configurable via environment variables for port and polling interval.
- **Docker Ready**: Includes a `Dockerfile` for easy containerized deployment.

## Metrics Exposed

| Metric Name                | Type  | Labels                                                                                  | Description                                       |
| -------------------------- | ----- | --------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `argocd_app_info`          | Gauge | `server`, `app_name`, `project`, `health_status`, `sync_status`, `namespace`, `cluster` | General information about the ArgoCD application. |
| `argocd_app_health_status` | Gauge | `server`, `app_name`, `project`, `namespace`, `cluster`                                 | 1 if Application is `Healthy`, 0 otherwise.       |
| `argocd_app_sync_status`   | Gauge | `server`, `app_name`, `project`, `namespace`, `cluster`                                 | 1 if Application is `Synced`, 0 otherwise.        |
| `argocd_up`                | Gauge | `server`                                                                                | 1 if the ArgoCD server is reachable, 0 otherwise. |

## Configuration

The exporter is configured entirely through environment variables.

| Variable        | Description                                          | Default |
| --------------- | ---------------------------------------------------- | ------- |
| `ARGOCD_CONFIG` | **Required**. A JSON array of server configurations. | N/A     |
| `PORT`          | The port on which the metrics server listens.        | `8000`  |
| `POLL_INTERVAL` | Time in seconds between scrapes of ArgoCD servers.   | `30`    |

### `ARGOCD_CONFIG` Format

```json
[
  {
    "server": "https://argocd-instance-1.com",
    "token": "your-api-token-1"
  },
  {
    "server": "https://argocd-instance-2.com",
    "token": "your-api-token-2"
  }
]
```

## Getting Started

### Local Development

1. Install `uv` if you haven't:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Set environment variables and run:
   ```bash
   export ARGOCD_CONFIG='[{"server": "https://your-argocd.com", "token": "your-token"}]'
   uv run exporter.py
   ```

### Docker

Build the image:

```bash
docker build -t argocd-exporter .
```

Run the container:

```bash
docker run -p 8000:8000 \
  -e ARGOCD_CONFIG='[{"server": "https://your-argocd.com", "token": "your-token"}]' \
  argocd-exporter
```

## Testing

The project uses `pytest` and `respx` for mock-based unit testing. Run tests with `uv`:

```bash
uv run pytest -v test_exporter.py
```
