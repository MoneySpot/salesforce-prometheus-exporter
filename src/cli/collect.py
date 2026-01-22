import logging
from os import environ
from typing import Optional

import requests
from prometheus_client.core import GaugeMetricFamily

# Default timeout for all HTTP requests (seconds)
REQUEST_TIMEOUT = 30

logging.basicConfig(level=logging.INFO)


class TenantConfig:
    """Configuration for a single Salesforce tenant/org."""

    def __init__(
        self,
        name: str,
        login_url: str,
        client_id: str,
        client_secret: str,
        version: str,
    ):
        self.name = name
        self.login_url = login_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.version = version

    def __repr__(self):
        return f"TenantConfig(name={self.name}, login_url={self.login_url})"


class TenantClient:
    """Client for fetching metrics from a single Salesforce tenant."""

    def __init__(self, config: TenantConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._instance_url: Optional[str] = None

    def get_access_token(self):
        """Authenticate using OAuth 2.0 Client Credentials flow."""
        logging.info(
            f"[{self.config.name}] Fetching access token using Client Credentials flow."
        )

        token_url = f"{self.config.login_url}/services/oauth2/token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        response = requests.post(token_url, data=payload, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            token_data = response.json()
            self._access_token = token_data["access_token"]
            self._instance_url = token_data["instance_url"]
            logging.info(f"[{self.config.name}] Successfully obtained access token.")
            return {
                "access_token": self._access_token,
                "instance_url": self._instance_url,
            }
        else:
            # Truncate error response to avoid leaking sensitive info
            error_text = response.text[:200] if response.text else "Unknown error"
            raise ConnectionRefusedError(
                f"[{self.config.name}] Failed to obtain access token: "
                f"[{response.status_code}] {error_text}"
            )

    def fetch_limits(self) -> dict:
        """Fetch Salesforce limits/logs for this tenant."""
        logging.info(f"[{self.config.name}] Fetching Salesforce limits.")
        credentials = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
        }

        response = requests.get(
            f"{credentials['instance_url']}/services/data/v{self.config.version}/limits",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            logging.info(f"[{self.config.name}] Limits fetched successfully.")
            return response.json()
        else:
            # Truncate error response to avoid leaking sensitive info
            error_text = response.text[:200] if response.text else "Unknown error"
            raise ConnectionError(
                f"[{self.config.name}] Failed to fetch limits: "
                f"[{response.status_code}] {error_text}"
            )


def load_tenants_from_env() -> list[TenantConfig]:
    """
    Load tenant configurations from environment variables.

    Supports two formats:

    1. Single tenant (legacy):
       SF_URL, SF_VERSION, CONSUMER_ID, CONSUMER_SECRET, ENVIRONMENT

    2. Multiple tenants:
       TENANTS=tenant1,tenant2,tenant3
       TENANT_TENANT1_URL=https://...
       TENANT_TENANT1_VERSION=57.0
       TENANT_TENANT1_CONSUMER_ID=...
       TENANT_TENANT1_CONSUMER_SECRET=...

       TENANT_TENANT2_URL=https://...
       TENANT_TENANT2_VERSION=57.0
       TENANT_TENANT2_CONSUMER_ID=...
       TENANT_TENANT2_CONSUMER_SECRET=...
    """
    tenants = []

    # Check for multi-tenant configuration
    tenant_names = environ.get("TENANTS", "").strip()

    if tenant_names:
        # Multi-tenant mode
        for name in tenant_names.split(","):
            name = name.strip().upper()
            if not name:
                continue

            prefix = f"TENANT_{name}_"

            url = environ.get(f"{prefix}URL")
            version = environ.get(f"{prefix}VERSION")
            client_id = environ.get(f"{prefix}CONSUMER_ID")
            client_secret = environ.get(f"{prefix}CONSUMER_SECRET")

            if not all([url, version, client_id, client_secret]):
                logging.warning(
                    f"Skipping tenant '{name}': missing required configuration. "
                    f"Need {prefix}URL, {prefix}VERSION, {prefix}CONSUMER_ID, {prefix}CONSUMER_SECRET"
                )
                continue

            tenants.append(
                TenantConfig(
                    name=name.lower(),
                    login_url=url,
                    version=version,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
            logging.info(f"Loaded tenant configuration: {name.lower()}")

    else:
        # Single tenant mode (legacy/fallback)
        url = environ.get("SF_URL")
        version = environ.get("SF_VERSION")
        client_id = environ.get("CONSUMER_ID")
        client_secret = environ.get("CONSUMER_SECRET")
        name = environ.get("ENVIRONMENT", "default")

        if all([url, version, client_id, client_secret]):
            tenants.append(
                TenantConfig(
                    name=name,
                    login_url=url,
                    version=version,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
            logging.info(f"Loaded single tenant configuration: {name}")
        else:
            logging.error(
                "No tenant configuration found. Set either TENANTS env var for multi-tenant, "
                "or SF_URL, SF_VERSION, CONSUMER_ID, CONSUMER_SECRET for single tenant."
            )

    return tenants


class Collector(object):
    """Prometheus collector that fetches metrics from multiple Salesforce orgs."""

    def __init__(self):
        self.tenants = load_tenants_from_env()
        self.clients = [TenantClient(config) for config in self.tenants]
        logging.info(f"Initialized collector with {len(self.clients)} tenant(s)")

    def _extract_metrics(
        self, logs: dict, tenant_name: str, metrics: dict, parent: Optional[str] = None
    ):
        """Extract metrics from logs into a dictionary keyed by metric name."""
        for key, value in logs.items():
            if parent:
                metric = f"{parent}".replace(" ", "_").replace(".", "_")

            if type(value) == dict:
                if parent:
                    new_parent = f"{parent}_{key}"
                else:
                    new_parent = key
                self._extract_metrics(
                    logs=value,
                    tenant_name=tenant_name,
                    metrics=metrics,
                    parent=new_parent,
                )
            elif key == "Remaining":
                metric_name = f"sfdc_remaining_{metric}"
                if metric_name not in metrics:
                    metrics[metric_name] = {
                        "help": f"{parent or ''} {key}",
                        "values": [],
                    }
                metrics[metric_name]["values"].append((tenant_name, value))
            elif key == "Max":
                metric_name = f"sfdc_limit_{metric}"
                if metric_name not in metrics:
                    metrics[metric_name] = {
                        "help": f"{parent or ''} {key}",
                        "values": [],
                    }
                metrics[metric_name]["values"].append((tenant_name, value))

    def collect(self):
        """Collect metrics from all configured tenants."""
        # Collect all metrics from all tenants into a single dict
        all_metrics = {}
        error_tenants = []

        for client in self.clients:
            try:
                logs = client.fetch_limits()
                self._extract_metrics(
                    logs=logs, tenant_name=client.config.name, metrics=all_metrics
                )
            except Exception as e:
                logging.error(f"[{client.config.name}] Error collecting metrics: {e}")
                error_tenants.append(client.config.name)

        # Yield grouped metrics
        for metric_name, data in all_metrics.items():
            gauge = GaugeMetricFamily(
                metric_name,
                data["help"],
                labels=["tenant"],
            )
            for tenant_name, value in data["values"]:
                gauge.add_metric([tenant_name], value)
            yield gauge

        # Yield error metrics if any
        if error_tenants:
            error_metric = GaugeMetricFamily(
                "sfdc_scrape_error",
                "Indicates an error occurred while scraping this tenant",
                labels=["tenant"],
            )
            for tenant_name in error_tenants:
                error_metric.add_metric([tenant_name], 1)
            yield error_metric
