# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:
https://github.com/sharad52/klyvion/security/advisories/new

You'll get an acknowledgment within 72 hours and a status update within
7 days. Please include reproduction steps and impact assessment if possible.

## Scope notes

- The HTTP server is designed to sit behind a reverse proxy
  (see `deploy/nginx.conf`); reports assuming direct internet exposure of
  the uvicorn port are still welcome but lower severity.
- Voice cloning misuse (impersonation) is an abuse concern rather than a
  code vulnerability; see the Ethics section of the README. Ideas for
  technical mitigations (consent checks, watermarking) belong in
  Discussions → Ideas.
