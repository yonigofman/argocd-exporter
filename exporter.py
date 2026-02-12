import os
import json
import logging
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from prometheus_client import start_http_server, Gauge

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Metrics
ARGOCD_APP_INFO = Gauge(
    'argocd_app_info',
    'Information about the ArgoCD application',
    ['server', 'app_name', 'project', 'health_status', 'sync_status', 'namespace', 'cluster']
)

ARGOCD_APP_HEALTH_STATUS = Gauge(
    'argocd_app_health_status',
    'Health status of the ArgoCD application (1 for Healthy, 0 otherwise)',
    ['server', 'app_name', 'project', 'namespace', 'cluster']
)

ARGOCD_APP_SYNC_STATUS = Gauge(
    'argocd_app_sync_status',
    'Sync status of the ArgoCD application (1 for Synced, 0 otherwise)',
    ['server', 'app_name', 'project', 'namespace', 'cluster']
)

ARGOCD_UP = Gauge(
    'argocd_up',
    'Status of the ArgoCD server connection (1 for Up, 0 for Down)',
    ['server']
)

async def fetch_apps(server_config: Dict[str, str]) -> Optional[Dict[str, Any]]:
    server_url = server_config['server'].rstrip('/')
    token = server_config['token']
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(f"{server_url}/api/v1/applications", headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch apps from {server_url}: {e}")
        return None

async def collect_metrics(config: List[Dict[str, str]]) -> None:
    for server_config in config:
        server_url = server_config['server']
        logger.info(f"Collecting metrics from {server_url}")
        
        data = await fetch_apps(server_config)
        
        if data:
            ARGOCD_UP.labels(server=server_url).set(1)
            items = data.get('items', [])
            
            for app in items:
                metadata = app.get('metadata', {})
                status = app.get('status', {})
                spec = app.get('spec', {})
                
                name = metadata.get('name', 'unknown')
                project = spec.get('project', 'unknown')
                namespace = metadata.get('namespace', 'unknown')
                
                destination = spec.get('destination', {})
                cluster = destination.get('server') or destination.get('name') or 'unknown'
                
                health_status = status.get('health', {}).get('status', 'Unknown')
                sync_status = status.get('sync', {}).get('status', 'Unknown')

                # Info metric
                ARGOCD_APP_INFO.labels(
                    server=server_url,
                    app_name=name,
                    project=project,
                    health_status=health_status,
                    sync_status=sync_status,
                    namespace=namespace,
                    cluster=cluster
                ).set(1)

                # Health status metric
                is_healthy = 1 if health_status == 'Healthy' else 0
                ARGOCD_APP_HEALTH_STATUS.labels(
                    server=server_url,
                    app_name=name,
                    project=project,
                    namespace=namespace,
                    cluster=cluster
                ).set(is_healthy)

                # Sync status metric
                is_synced = 1 if sync_status == 'Synced' else 0
                ARGOCD_APP_SYNC_STATUS.labels(
                    server=server_url,
                    app_name=name,
                    project=project,
                    namespace=namespace,
                    cluster=cluster
                ).set(is_synced)
        else:
            ARGOCD_UP.labels(server=server_url).set(0)

async def main() -> None:
    # Parse configuration
    config_str = os.environ.get('ARGOCD_CONFIG')
    if not config_str:
        logger.error("ARGOCD_CONFIG environment variable is not set")
        return

    try:
        config = json.loads(config_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ARGOCD_CONFIG: {e}")
        return

    # Helper function to get int from env or default
    def get_env_int(key: str, default: int) -> int:
        try:
            return int(os.environ.get(key, default))
        except ValueError:
            return default

    port = get_env_int('PORT', 8000)
    poll_interval = get_env_int('POLL_INTERVAL', 30)

    logger.info(f"Starting ArgoCD Exporter with {len(config)} servers on port {port}")

    # Start Prometheus HTTP server
    start_http_server(port)
    
    while True:
        await collect_metrics(config)
        await asyncio.sleep(poll_interval)

if __name__ == '__main__':
    asyncio.run(main())
