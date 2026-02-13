import os
import asyncio
import logging
import httpx
from typing import List, Dict, Any
from pydantic import BaseModel, Field, TypeAdapter
from prometheus_client import start_http_server, Gauge

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArgoServerConfig(BaseModel):
    server: str
    token: str

class ExporterConfig(BaseModel):
    servers: List[ArgoServerConfig]
    port: int = Field(default=8000)
    poll_interval: int = Field(default=30)


METRICS = {
    "info": Gauge('argocd_app_info', 'App metadata', 
                  ['server', 'app_name', 'project', 'health_status', 'sync_status', 'namespace', 'cluster']),
    "health": Gauge('argocd_app_health_status', '1=Healthy', 
                    ['server', 'app_name', 'project', 'namespace', 'cluster']),
    "sync": Gauge('argocd_app_sync_status', '1=Synced', 
                  ['server', 'app_name', 'project', 'namespace', 'cluster']),
    "up": Gauge('argocd_up', 'ArgoCD API Reachability', ['server'])
}

class ArgoExporter:
    def __init__(self, config: ExporterConfig):
        self.config = config
        self.client = httpx.AsyncClient(verify=False, timeout=10.0)

    async def fetch_and_record(self, server_cfg: ArgoServerConfig):
        url = f"{server_cfg.server.rstrip('/')}/api/v1/applications"
        headers = {'Authorization': f'Bearer {server_cfg.token}'}
        
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            METRICS["up"].labels(server=server_cfg.server).set(1)
            self._process_apps(server_cfg.server, data.get('items', []))
            
        except Exception as e:
            logger.error(f"Scrape failed for {server_cfg.server}: {str(e)}")
            METRICS["up"].labels(server=server_cfg.server).set(0)

    def _process_apps(self, server_url: str, items: List[Dict]):
        for app in items:
            meta = app.get('metadata', {})
            spec = app.get('spec', {})
            status = app.get('status', {})
            
            name = meta.get('name', 'unknown')
            project = spec.get('project', 'default')
            namespace = meta.get('namespace', 'unknown')
            dest = spec.get('destination', {})
            cluster = dest.get('server') or dest.get('name') or 'unknown'
            
            h_stat = status.get('health', {}).get('status', 'Unknown')
            s_stat = status.get('sync', {}).get('status', 'Unknown')

            # Update Metrics
            METRICS["info"].labels(
                server=server_url, app_name=name, project=project,
                health_status=h_stat, sync_status=s_stat,
                namespace=namespace, cluster=cluster
            ).set(1)

            METRICS["health"].labels(
                server=server_url, app_name=name, project=project,
                namespace=namespace, cluster=cluster
            ).set(1 if h_stat == 'Healthy' else 0)

            METRICS["sync"].labels(
                server=server_url, app_name=name, project=project,
                namespace=namespace, cluster=cluster
            ).set(1 if s_stat == 'Synced' else 0)

    async def run_loop(self):
        start_http_server(self.config.port)
        logger.info(f"Exporter listening on port {self.config.port}")
        
        while True:
            for m in METRICS.values(): m.clear()
            
            tasks = [self.fetch_and_record(s) for s in self.config.servers]
            await asyncio.gather(*tasks)
            
            await asyncio.sleep(self.config.poll_interval)

async def main():
    try:
        raw_config = os.environ.get('ARGOCD_CONFIG', '[]')
        servers = TypeAdapter(List[ArgoServerConfig]).validate_json(raw_config)
        
        config = ExporterConfig(
            servers=servers,
            port=int(os.environ.get('PORT', 8000)),
            poll_interval=int(os.environ.get('POLL_INTERVAL', 30))
        )
    except Exception as e:
        logger.critical(f"Config validation failed: {e}")
        return

    exporter = ArgoExporter(config)
    await exporter.run_loop()

if __name__ == '__main__':
    asyncio.run(main())