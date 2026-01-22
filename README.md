# Salesforce Prometheus Exporter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Forked from](https://img.shields.io/badge/forked%20from-hippo--oss-lightgrey)](https://github.com/hippo-oss/salesforce-prometheus-exporter)
[![GitHub](https://img.shields.io/github/stars/moneyspot/salesforce-prometheus-exporter?style=social)](https://github.com/moneyspot/salesforce-prometheus-exporter)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A Prometheus exporter for Salesforce org limits and metrics. Supports multiple tenants/orgs and uses OAuth 2.0 Client Credentials flow for secure authentication.

## Features

- **OAuth 2.0 Client Credentials** - No username/password required
- **Multi-tenant** - Monitor multiple Salesforce orgs from a single instance
- **API Key Authentication** - Protect your metrics endpoint
- **Docker Ready** - Minimal Alpine-based image, runs as non-root
- **Fly.io Ready** - Deploy in minutes

### Getting Started

To Build the docker:
```shell
docker build -t salesforce-prometheus-exporter .
```

Create a file with following environment variables.  For e.g. `/tmp/env.list`

### Single Tenant Configuration

```shell
SF_URL=<salesforce url>
SF_VERSION=<salesforce version>
CONSUMER_ID=<salesforce consumer/client ID>
CONSUMER_SECRET=<salesforce consumer/client secret>
ENVIRONMENT=<dev|qa|production> # default is set to `local`, used as tenant label
API_KEY=<your-secret-api-key> # optional, protects /metrics endpoint
```

### Multi-Tenant Configuration

To scrape metrics from multiple Salesforce orgs, use the `TENANTS` env var:

```shell
# Comma-separated list of tenant names
TENANTS=production,sandbox,dev

# Configuration for each tenant (prefix: TENANT_<NAME>_)
TENANT_PRODUCTION_URL=https://mycompany.my.salesforce.com
TENANT_PRODUCTION_VERSION=57.0
TENANT_PRODUCTION_CONSUMER_ID=<consumer id>
TENANT_PRODUCTION_CONSUMER_SECRET=<consumer secret>

TENANT_SANDBOX_URL=https://mycompany--sandbox.sandbox.my.salesforce.com
TENANT_SANDBOX_VERSION=57.0
TENANT_SANDBOX_CONSUMER_ID=<consumer id>
TENANT_SANDBOX_CONSUMER_SECRET=<consumer secret>

TENANT_DEV_URL=https://mycompany--dev.sandbox.my.salesforce.com
TENANT_DEV_VERSION=57.0
TENANT_DEV_CONSUMER_ID=<consumer id>
TENANT_DEV_CONSUMER_SECRET=<consumer secret>

API_KEY=<your-secret-api-key> # optional, protects /metrics endpoint
```

Metrics will include a `tenant` label to distinguish between orgs:
```
sfdc_remaining_DailyApiRequests{tenant="production"} 14999
sfdc_remaining_DailyApiRequests{tenant="sandbox"} 14500
```

**Note:** This exporter uses the OAuth 2.0 Client Credentials flow. You need to configure a Connected App in each Salesforce org with the "Client Credentials Flow" enabled.

### Authentication

The `/metrics` endpoint can be protected with an API key. Set the `API_KEY` environment variable to enable authentication.

**Supported authentication methods:**

1. **Bearer Token** (recommended):
   ```shell
   curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:3000/metrics
   ```

2. **X-API-Key Header**:
   ```shell
   curl -H "X-API-Key: YOUR_API_KEY" http://localhost:3000/metrics
   ```

3. **Query Parameter** (for testing only):
   ```shell
   curl "http://localhost:3000/metrics?api_key=YOUR_API_KEY"
   ```

**Prometheus configuration example:**
```yaml
scrape_configs:
  - job_name: 'salesforce'
    static_configs:
      - targets: ['localhost:3000']
    authorization:
      type: Bearer
      credentials: YOUR_API_KEY
```

**Rotating the API key:** Simply update the `API_KEY` environment variable and restart the container.

If `API_KEY` is not set, the `/metrics` endpoint will be unprotected. The `/health` endpoint is always unprotected.
Then, start server command:

```shell
docker run -p 3000:3000 --env-file /tmp/env.list salesforce-prometheus-exporter:latest
```
Go to http://localhost:3000/metrics to view the metrics.

### Available Routes:
<b>Home:</b> http://localhost:3000/ <br />
<b>Health:</b> http://localhost:3000/health <br />
<b>Metrics:</b> http://localhost:3000/metrics <br />

NOTE: The metrics will start with the prefix `sfdc`

## Acknowledgments

This project is a fork of [hippo-oss/salesforce-prometheus-exporter](https://github.com/hippo-oss/salesforce-prometheus-exporter), originally created by [Hippo Engineering](https://github.com/hippo-oss).

### Changes from Original

- Replaced username/password authentication with OAuth 2.0 Client Credentials flow
- Added multi-tenant support for monitoring multiple Salesforce orgs
- Added API key authentication for the `/metrics` endpoint
- Updated dependencies for Python 3.10+ compatibility
- Added Fly.io deployment configuration
- Security hardening (request timeouts, constant-time auth comparison, non-root container)
- Grouped Prometheus metrics output
- Custom Queries

## Custom Queries

You can define custom SOQL queries to expose as Prometheus metrics. 

> [!WARNING]  
> This may dramatically increase the time it takes for metrics to be returned.

Create a YAML config file:

```yaml
# queries.yml
metrics:
  # Simple count query - runs on all tenants
  - name: sfdc_account_count
    description: Total number of accounts
    query: SELECT COUNT() FROM Account
    value_field: totalSize

  # Query restricted to specific tenants
  - name: sfdc_sandbox_leads
    description: Lead count (sandbox only)
    query: SELECT COUNT() FROM Lead
    value_field: totalSize
    tenants:
      - sandbox
      - dev
```

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Prometheus metric name |
| `description` | Yes | Metric help text |
| `query` | Yes | SOQL query to execute |
| `value_field` | Yes | Field name containing the numeric value |
| `labels` | No | Additional label names for the metric |
| `label_fields` | No | SOQL fields to use as label values (must match `labels` order) |
| `tenants` | No | List of tenant names to run this query on (omit for all tenants) |

### Security: Custom Labels

⚠️ **Queries with custom labels are disabled by default** to prevent accidental data leakage.

When you use `labels` and `label_fields`, the actual field values from Salesforce become Prometheus label values. This could expose sensitive data (e.g., customer names, email addresses) in your metrics.

To enable queries with custom labels, set the environment variable:

```shell
ALLOW_CUSTOM_LABELS=true
```

**Best practices:**
- Only enable custom labels if you understand the security implications
- Use aggregate queries (COUNT, SUM, AVG) instead of row-level data when possible
- Always include `LIMIT` clauses in queries to prevent excessive data retrieval
- Avoid using PII fields (Email, Phone, Name, etc.) as label fields

**Example with labels (requires ALLOW_CUSTOM_LABELS=true):**

```yaml
metrics:
  - name: sfdc_opportunity_amount_by_stage
    description: Total opportunity amount by stage
    query: SELECT StageName, SUM(Amount) total FROM Opportunity GROUP BY StageName LIMIT 50
    value_field: total
    labels:
      - stage
    label_fields:
      - StageName
```

### Usage

Edit the `queries.yml` file in the repository root with your custom queries, then rebuild the Docker image:

```shell
# Edit queries.yml with your custom queries
# Then rebuild the image
docker build -t salesforce-prometheus-exporter .

# Run as usual - queries.yml is baked into the image
docker run -p 3000:3000 --env-file /tmp/env.list salesforce-prometheus-exporter:latest

# To enable custom labels (if needed)
docker run -p 3000:3000 -e ALLOW_CUSTOM_LABELS=true --env-file /tmp/env.list salesforce-prometheus-exporter:latest
```

The `queries.yml` file is automatically copied into the container at `/config/queries.yml` during the build.

To disable custom queries, leave all metrics commented out in `queries.yml`.

### Example Output

```
# HELP sfdc_account_count Total number of accounts
# TYPE sfdc_account_count gauge
sfdc_account_count{tenant="production"} 15234
sfdc_account_count{tenant="sandbox"} 892
```

#### Output with labels enabled

```
# HELP sfdc_opportunity_amount Total opportunity amount by stage
# TYPE sfdc_opportunity_amount gauge
sfdc_opportunity_amount{tenant="production",stage="Closed Won"} 1250000
sfdc_opportunity_amount{tenant="production",stage="Negotiation"} 500000
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Fly.io Deployment

### Prerequisites

1. Install the [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/)
2. Login to Fly: `fly auth login`

### Deploy

```shell
# Launch the app (first time only)
fly launch --no-deploy

# Set your secrets (single tenant)
fly secrets set \
  SF_URL=https://yourcompany.my.salesforce.com \
  SF_VERSION=57.0 \
  CONSUMER_ID=your_consumer_id \
  CONSUMER_SECRET=your_consumer_secret \
  ENVIRONMENT=production \
  API_KEY=your_secret_api_key

# Or for multi-tenant
fly secrets set \
  TENANTS=prod,sandbox \
  TENANT_PROD_URL=https://yourcompany.my.salesforce.com \
  TENANT_PROD_VERSION=57.0 \
  TENANT_PROD_CONSUMER_ID=your_consumer_id \
  TENANT_PROD_CONSUMER_SECRET=your_consumer_secret \
  TENANT_SANDBOX_URL=https://yourcompany--sandbox.sandbox.my.salesforce.com \
  TENANT_SANDBOX_VERSION=57.0 \
  TENANT_SANDBOX_CONSUMER_ID=your_consumer_id \
  TENANT_SANDBOX_CONSUMER_SECRET=your_consumer_secret \
  API_KEY=your_secret_api_key

# Deploy
fly deploy

# Check status
fly status
fly logs
```

### Prometheus Configuration (Fly.io)

```yaml
scrape_configs:
  - job_name: 'salesforce'
    static_configs:
      - targets: ['salesforce-prometheus-exporter.fly.dev']
    scheme: https
    authorization:
      type: Bearer
      credentials: YOUR_API_KEY
```

### Useful Commands

```shell
# View logs
fly logs

# SSH into the container
fly ssh console

# Scale up/down
fly scale count 2

# View secrets (names only)
fly secrets list

# Update a secret
fly secrets set API_KEY=new_api_key
```
