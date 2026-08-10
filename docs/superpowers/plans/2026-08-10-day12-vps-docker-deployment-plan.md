# Day 12 VPS Docker Deployment Plan

## Goal

Publish `huygoodboy/day12-agent` to Docker Hub, run the agent and Redis on the
VPS at `103.77.241.150`, and serve the verified API at
`https://day12.huygoodboy.io.vn` through Nginx and Certbot.

## Sequence

1. Reconcile the current production-hardening changes without staging the
   student's unrelated checklist edit or Railway-only working change.
2. Add a VPS Compose file that pulls an immutable image tag, binds the agent to
   loopback, keeps Redis private, and defines health/restart behavior.
3. Add a versioned HTTP Nginx reverse-proxy template for the target hostname.
4. Compile the Python sources, run the readiness checker, scan for tracked
   secrets, and validate Compose configuration.
5. Commit the exact source and deployment artifacts that will form the image.
6. Build `linux/amd64` image tags from that commit, run local container checks,
   confirm non-root execution and absence of `.env`, then push immutable and
   `latest` tags to Docker Hub.
7. Bootstrap a temporary task-specific SSH key using the provided password in
   process memory, then use key authentication for the remaining automation.
8. Inventory the VPS. Continue automatically only for supported Ubuntu/Debian
   with sufficient disk and an AMD64-compatible architecture.
9. Install Docker Engine and Compose from Docker's official APT repository;
   install Nginx and Certbot prerequisites from supported repositories.
10. Create `/opt/day12-agent`, generate application secrets on the VPS, copy
    Compose/Nginx artifacts, pull the immutable image, and start Redis plus the
    agent.
11. Validate local VPS health, Redis-backed rate limiting, Nginx configuration,
    firewall exposure, and HTTP service behavior.
12. Ask the user to add the `day12` A record pointing to the VPS, then wait for
    public DNS propagation and port-80 validation.
13. Issue the Let's Encrypt certificate, redirect HTTP to HTTPS, test renewal,
    and run the full remote smoke test without exposing the API key.
14. Update submission documentation/evidence, commit and push the final repo,
    then remove the temporary deployment key from the VPS and local temp area.

## Stop Conditions

- Docker Hub authentication cannot push to the selected namespace.
- The VPS host key no longer matches the user's accepted `known_hosts` entry.
- The VPS OS or CPU is unsupported by the approved design.
- A command would overwrite an unknown existing service or firewall rule.
- DNS does not resolve the hostname to `103.77.241.150`.
- Certbot would run before HTTP is publicly reachable.

## Required Evidence

- Static readiness 20/20.
- Successful Linux AMD64 image build and Docker Hub push.
- Non-root container identity and no embedded `.env`.
- Healthy agent and Redis containers on the VPS.
- Public HTTP before TLS and valid HTTPS after Certbot.
- Auth 401/200, JWT 200, metrics 200, and rate-limit 429.
- Successful `certbot renew --dry-run`.
- Final Git secret scan and clean staged scope.
