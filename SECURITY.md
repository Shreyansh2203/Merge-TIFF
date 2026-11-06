# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest | ✅ |

## Reporting a Vulnerability

If you discover a security vulnerability in Merge-TIFF, please report it responsibly.

**Do NOT** open a public GitHub issue for security vulnerabilities.

### How to Report

1. Email: [main.doga@gmail.com](mailto:main.doga@gmail.com) with subject "Merge-TIFF Security Vulnerability"
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 7 days
- **Fix release**: Within 14 days (critical), 30 days (non-critical)

### Security Measures

- Filename sanitization strips control bytes and path separators before writing TIFF tags
- Request/response size caps (4MB) prevent payload-too-large attacks
- Pixel budget (50MP) prevents decompression-bomb memory exhaustion
- Rate limiting per client IP (30 req/60s)
- CodeQL SAST scanning on every push
- Dependency Review on pull requests
- Bandit Python security scanning

### Disclosure Policy

- Vulnerabilities are disclosed after a fix is released
- Credit is given to the reporter (unless they prefer anonymity)
- Public disclosure timeline: 90 days after fix release

## Security Contacts

- **Maintainer**: Shreyansh Srivastava ([@Shreyansh2203](https://github.com/Shreyansh2203))
- **Email**: main.doga@gmail.com