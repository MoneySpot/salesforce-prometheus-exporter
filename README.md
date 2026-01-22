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
