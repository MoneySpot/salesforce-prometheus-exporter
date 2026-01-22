# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainers directly at: security@moneyspot.com.au
3. Include the following in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 72 hours
- **Updates**: We will provide updates on the status of your report within 10 days
- **Resolution**: We aim to resolve critical vulnerabilities within 14 days
- **Disclosure**: We will coordinate with you on public disclosure timing

### Scope

The following are in scope for security reports:

- Authentication bypass
- Credential exposure
- API key leakage
- Injection vulnerabilities
- Denial of service vulnerabilities
- Container security issues

### Out of Scope

- Vulnerabilities in dependencies (please report these to the respective projects)
- Issues requiring physical access
- Social engineering attacks

## Security Best Practices

When deploying this exporter:

1. **Always set an API key** - Use the `API_KEY` environment variable to protect the `/metrics` endpoint
2. **Use HTTPS** - Deploy behind a reverse proxy with TLS termination
3. **Rotate credentials** - Periodically rotate your Salesforce OAuth credentials and API keys
4. **Limit network access** - Restrict access to the exporter to your Prometheus server only
5. **Monitor logs** - Watch for authentication failures and unusual access patterns
