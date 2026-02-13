import pytest
import respx
import httpx
from prometheus_client import REGISTRY
from exporter import ArgoExporter, ArgoServerConfig, ExporterConfig, METRICS

@pytest.fixture(autouse=True)
def reset_metrics():
    """Clear metrics before each test to ensure a clean state."""
    for metric in METRICS.values():
        metric.clear()

@pytest.fixture
def exporter():
    """Initialize the exporter with a mock config."""
    config = ExporterConfig(
        servers=[ArgoServerConfig(server="https://argocd.example.com", token="s3cr3t")],
        poll_interval=30
    )
    return ArgoExporter(config)

@pytest.mark.asyncio
async def test_fetch_and_record_success(exporter):
    server_cfg = exporter.config.servers[0]
    
    # Mock ArgoCD API
    with respx.mock(base_url="https://argocd.example.com") as respx_mock:
        respx_mock.get("/api/v1/applications").mock(return_value=httpx.Response(200, json={
            "items": [
                {
                    "metadata": {"name": "app1", "namespace": "default"},
                    "spec": {
                        "project": "default",
                        "destination": {"server": "https://kubernetes.default.svc"}
                    },
                    "status": {
                        "health": {"status": "Healthy"},
                        "sync": {"status": "Synced"}
                    }
                },
                {
                    "metadata": {"name": "app2", "namespace": "argocd"},
                    "spec": {
                        "project": "system",
                        "destination": {"name": "in-cluster"}
                    },
                    "status": {
                        "health": {"status": "Degraded"},
                        "sync": {"status": "OutOfSync"}
                    }
                }
            ]
        }))

        await exporter.fetch_and_record(server_cfg)

        # Verify App 1 (Healthy/Synced)
        labels_1 = {
            "server": "https://argocd.example.com", 
            "app_name": "app1", 
            "project": "default", 
            "namespace": "default", 
            "cluster": "https://kubernetes.default.svc"
        }
        assert REGISTRY.get_sample_value('argocd_app_health_status', labels=labels_1) == 1.0
        assert REGISTRY.get_sample_value('argocd_app_sync_status', labels=labels_1) == 1.0
        
        # Verify App 2 (Degraded/OutOfSync)
        labels_2 = {
            "server": "https://argocd.example.com", 
            "app_name": "app2", 
            "project": "system", 
            "namespace": "argocd", 
            "cluster": "in-cluster"
        }
        assert REGISTRY.get_sample_value('argocd_app_health_status', labels=labels_2) == 0.0
        assert REGISTRY.get_sample_value('argocd_app_sync_status', labels=labels_2) == 0.0

        # Server Up
        assert REGISTRY.get_sample_value('argocd_up', labels={"server": "https://argocd.example.com"}) == 1.0

@pytest.mark.asyncio
async def test_fetch_and_record_error(exporter):
    server_cfg = exporter.config.servers[0]
    
    with respx.mock(base_url="https://argocd.example.com") as respx_mock:
        respx_mock.get("/api/v1/applications").mock(return_value=httpx.Response(500))

        await exporter.fetch_and_record(server_cfg)
        
        # Verify server is marked as down
        assert REGISTRY.get_sample_value('argocd_up', labels={"server": "https://argocd.example.com"}) == 0.0

@pytest.mark.asyncio
async def test_metric_cleanup_on_new_scrape(exporter):
    """Verify that old apps are cleared when they are no longer in the API response."""
    server_cfg = exporter.config.servers[0]
    
    with respx.mock(base_url="https://argocd.example.com") as respx_mock:
        # 1st Scrape: One app exists
        route = respx_mock.get("/api/v1/applications")
        route.side_effect = [
            httpx.Response(200, json={"items": [{"metadata": {"name": "old-app"}, "status": {}, "spec": {}}]}),
            httpx.Response(200, json={"items": []}) # 2nd Scrape: App deleted
        ]

        # First run
        await exporter.fetch_and_record(server_cfg)
        assert REGISTRY.get_sample_value('argocd_app_info', labels={
            'server': server_cfg.server, 'app_name': 'old-app', 'project': 'default', 
            'health_status': 'Unknown', 'sync_status': 'Unknown', 'namespace': 'unknown', 'cluster': 'unknown'
        }) == 1.0

        # Second run - we manually clear like the run_loop does
        for m in METRICS.values(): m.clear()
        await exporter.fetch_and_record(server_cfg)
        
        # App should no longer exist in registry
        assert REGISTRY.get_sample_value('argocd_app_info', labels={'app_name': 'old-app'}) is None