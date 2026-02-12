import pytest
import respx
import httpx
from prometheus_client import REGISTRY
from exporter import collect_metrics

@pytest.mark.asyncio
async def test_collect_metrics():
    # Mock configuration
    config = [{"server": "https://argocd.example.com", "token": "s3cr3t"}]
    
    # Mock ArgoCD API
    async with respx.mock(base_url="https://argocd.example.com") as respx_mock:
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

        await collect_metrics(config)

        # Verify metrics
        # App 1
        assert REGISTRY.get_sample_value('argocd_app_health_status', labels={"server": "https://argocd.example.com", "app_name": "app1", "project": "default", "namespace": "default", "cluster": "https://kubernetes.default.svc"}) == 1.0
        assert REGISTRY.get_sample_value('argocd_app_sync_status', labels={"server": "https://argocd.example.com", "app_name": "app1", "project": "default", "namespace": "default", "cluster": "https://kubernetes.default.svc"}) == 1.0
        
        # App 2
        assert REGISTRY.get_sample_value('argocd_app_health_status', labels={"server": "https://argocd.example.com", "app_name": "app2", "project": "system", "namespace": "argocd", "cluster": "in-cluster"}) == 0.0
        assert REGISTRY.get_sample_value('argocd_app_sync_status', labels={"server": "https://argocd.example.com", "app_name": "app2", "project": "system", "namespace": "argocd", "cluster": "in-cluster"}) == 0.0

        # Server Up
        assert REGISTRY.get_sample_value('argocd_up', labels={"server": "https://argocd.example.com"}) == 1.0

@pytest.mark.asyncio
async def test_collect_metrics_error():
    config = [{"server": "https://argocd.bad.com", "token": "s3cr3t"}]
    
    async with respx.mock(base_url="https://argocd.bad.com") as respx_mock:
        respx_mock.get("/api/v1/applications").mock(return_value=httpx.Response(500))

        await collect_metrics(config)
        
        assert REGISTRY.get_sample_value('argocd_up', labels={"server": "https://argocd.bad.com"}) == 0.0
