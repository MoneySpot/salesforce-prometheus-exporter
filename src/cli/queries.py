"""Custom SOQL queries module for user-defined Prometheus metrics."""

import logging
import os
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests
import yaml  # type: ignore[import-untyped]
from prometheus_client.core import GaugeMetricFamily, Metric

from cli.collect import (
    REQUEST_TIMEOUT,
    TenantClient,
    load_tenants_from_env,
)

logging.basicConfig(level=logging.INFO)


@dataclass
class QueryMetric:
    """Configuration for a single custom metric from a SOQL query."""

    name: str
    description: str
    query: str
    value_field: str
    labels: List[str] = field(default_factory=list)
    label_fields: List[str] = field(default_factory=list)
    tenants: Optional[List[str]] = None  # None means all tenants


@dataclass
class QueriesConfig:
    """Configuration for all custom queries."""

    metrics: List[QueryMetric] = field(default_factory=list)


# Default config path (baked into Docker image)
DEFAULT_QUERIES_CONFIG_PATH = "/config/queries.yml"


def load_queries_config(config_path: Optional[str] = None) -> QueriesConfig:
    """
    Load custom queries configuration from a YAML file.

    Args:
        config_path: Path to the config file. Defaults to /config/queries.yml.

    Returns:
        QueriesConfig object with parsed metrics.
    """
    path = config_path or DEFAULT_QUERIES_CONFIG_PATH

    config_file = Path(path)
    if not config_file.exists():
        logging.debug(f"Queries config file not found: {path}")
        return QueriesConfig()

    try:
        with open(config_file, "r") as f:
            raw_config = yaml.safe_load(f)

        if not raw_config or "metrics" not in raw_config:
            logging.warning(f"No metrics defined in {path}")
            return QueriesConfig()

        metrics = []
        for m in raw_config.get("metrics", []):
            if not all(k in m for k in ["name", "description", "query", "value_field"]):
                logging.warning(f"Skipping invalid metric config: {m}")
                continue

            metrics.append(
                QueryMetric(
                    name=m["name"],
                    description=m["description"],
                    query=m["query"],
                    value_field=m["value_field"],
                    labels=m.get("labels", []),
                    label_fields=m.get("label_fields", []),
                    tenants=m.get("tenants"),  # None means all tenants
                )
            )

        logging.info(f"Loaded {len(metrics)} custom query metric(s) from {path}")
        return QueriesConfig(metrics=metrics)

    except yaml.YAMLError as e:
        logging.error(f"Failed to parse queries config: {e}")
        return QueriesConfig()
    except Exception as e:
        logging.error(f"Failed to load queries config: {e}")
        return QueriesConfig()


class QueryClient:
    """Client for executing SOQL queries against a Salesforce tenant."""

    def __init__(self, tenant_client: TenantClient):
        self.tenant_client = tenant_client

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a SOQL query and return the results.

        Args:
            query: SOQL query string

        Returns:
            List of record dictionaries
        """
        credentials = self.tenant_client.get_access_token()

        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }

        # URL-encode the query
        encoded_query = urllib.parse.quote(query)

        url = (
            f"{credentials['instance_url']}/services/data/"
            f"v{self.tenant_client.config.version}/query?q={encoded_query}"
        )

        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])

            # For COUNT() queries, Salesforce returns totalSize but empty records
            # Inject totalSize as a pseudo-record so it can be extracted
            if not records and "totalSize" in data:
                records = [{"totalSize": data["totalSize"]}]

            return records
        else:
            error_text = response.text[:200] if response.text else "Unknown error"
            raise ConnectionError(
                f"[{self.tenant_client.config.name}] Query failed: "
                f"[{response.status_code}] {error_text}"
            )


class CustomQueryCollector:
    """Prometheus collector for custom SOQL query metrics."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = load_queries_config(config_path)
        self.tenants = load_tenants_from_env()
        self.clients = [QueryClient(TenantClient(tenant)) for tenant in self.tenants]
        logging.info(
            f"CustomQueryCollector initialized with {len(self.config.metrics)} metric(s) "
            f"and {len(self.clients)} tenant(s)"
        )

    def collect(self) -> Iterator[Metric]:
        """Collect custom query metrics from all tenants."""
        if not self.config.metrics:
            return

        allow_custom_labels = (
            os.environ.get("ALLOW_CUSTOM_LABELS", "false").lower() == "true"
        )

        if allow_custom_labels:
            logging.warning(
                "ALLOW_CUSTOM_LABELS is enabled - custom labels may expose sensitive data"
            )

        for metric_config in self.config.metrics:
            # Skip queries with labels if not allowed
            if (
                metric_config.labels or metric_config.label_fields
            ) and not allow_custom_labels:
                logging.debug(
                    f"Skipping metric '{metric_config.name}' - has labels but ALLOW_CUSTOM_LABELS=false"
                )
                continue

            # Create gauge with tenant label + any custom labels
            all_labels = ["tenant"] + metric_config.labels

            gauge = GaugeMetricFamily(
                metric_config.name,
                metric_config.description,
                labels=all_labels,
            )

            for client in self.clients:
                tenant_name = client.tenant_client.config.name

                # Skip if this metric is restricted to specific tenants
                if metric_config.tenants is not None:
                    if tenant_name not in metric_config.tenants:
                        continue

                try:
                    records = client.execute_query(metric_config.query)
                    logging.debug(
                        f"[{tenant_name}] Query '{metric_config.name}' returned: {records}"
                    )

                    if not records:
                        logging.debug(
                            f"[{tenant_name}] No results for query: {metric_config.name}"
                        )
                        continue

                    for record in records:
                        # Extract the value
                        value = record.get(metric_config.value_field)
                        if value is None:
                            logging.warning(
                                f"[{tenant_name}] Field '{metric_config.value_field}' "
                                f"not found in query result for {metric_config.name}"
                            )
                            continue

                        # Convert to float
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            logging.warning(
                                f"[{tenant_name}] Cannot convert value '{value}' "
                                f"to float for {metric_config.name}"
                            )
                            continue

                        # Build label values
                        label_values = [tenant_name]
                        for label_field in metric_config.label_fields:
                            label_value = record.get(label_field, "unknown")
                            label_values.append(
                                str(label_value) if label_value else "null"
                            )

                        logging.debug(
                            f"[{tenant_name}] Metric '{metric_config.name}': "
                            f"labels={all_labels}, values={label_values}, value={value}"
                        )
                        gauge.add_metric(label_values, value)

                except Exception as e:
                    logging.error(
                        f"[{tenant_name}] Error executing query for "
                        f"{metric_config.name}: {e}"
                    )

            yield gauge

        # Yield a metric indicating custom queries are enabled
        info_metric = GaugeMetricFamily(
            "sfdc_custom_queries_configured",
            "Number of custom query metrics configured",
            labels=[],
        )
        info_metric.add_metric([], len(self.config.metrics))
        yield info_metric
