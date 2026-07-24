# Security Policy

## Supported version

The latest published preview or stable release receives security fixes.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue before a fix
is available. Use the repository's private
[GitHub Security Advisory](https://github.com/SultanAlfaifi/mustakshif/security/advisories/new)
reporting flow. If that form is unavailable, contact Sultan Alfaifi through:

- X: https://x.com/SultAlfaifi
- LinkedIn: https://www.linkedin.com/in/alfaifi-sultan/

Include the affected version, reproduction steps, expected impact, and any
suggested mitigation. Do not include secrets or personal data.

## Security principles

- Hardware inspection remains local.
- Network requests are limited to allowlisted HTTPS sources.
- Model installation is approval-gated.
- Install commands are executed as argument arrays without shell interpolation.
- Unknown model layouts are not guessed or automatically trusted.
