# Day 12 VPS Docker Deployment Design

## Status and Context

This design supersedes the earlier Railway Free deployment design for the
current implementation. The target is a user-owned VPS reachable as root at
`103.77.241.150`, with the public hostname `day12.huygoodboy.io.vn`.

The application already exists in `06-lab-complete`. The working tree contains
uncommitted production-hardening changes from the interrupted Railway path:
non-root Docker execution, dynamic port handling, a ten-request rate limit,
unique Redis sliding-window members, and a stricter smoke test. Relevant changes
will be retained and adapted to the VPS deployment; Railway-only configuration
will not drive the VPS runtime.

Docker Desktop 28.3.0 is available locally with an authenticated Docker Hub
credential store. The selected public image repository is
`huygoodboy/day12-agent`. The hostname does not yet resolve to the VPS, and
ports 80 and 443 are not yet serving the application.

## Objective

Build and verify a Linux AMD64 image locally, push immutable and rolling tags to
Docker Hub, provision Docker on the empty VPS, pull and run the agent with Redis,
publish it through Nginx, and issue a Let's Encrypt certificate with Certbot for
`day12.huygoodboy.io.vn`.

The final deployment must be reproducible, use no secret from the Git
repository, expose only SSH/HTTP/HTTPS publicly, and provide a tested rollback
path.

## Chosen Architecture

```text
Internet
    |
    | TCP 80/443
    v
Host Nginx + Certbot
    |
    | http://127.0.0.1:8000
    v
Docker Compose private network
    |-- FastAPI agent (public Docker Hub image, non-root container user)
    `-- Redis (no host port, persistent named volume)
```

Nginx and Certbot run on the host. The application and Redis run through Docker
Compose. This keeps certificate issuance and renewal conventional while keeping
the application packaging and state service reproducible.

An all-container Nginx/Certbot layout was rejected because certificate volumes,
renewal hooks, and bootstrap ordering would add complexity without improving
this single-VPS lab. Running FastAPI directly under systemd was rejected because
it would bypass the requested Docker Hub pull workflow.

## Scope

### Included

- Reconcile the existing Dockerfile into a Linux AMD64, multi-stage, non-root
  image.
- Add a VPS Compose definition that pulls `huygoodboy/day12-agent`.
- Build and test the image locally, then push both a Git-derived immutable tag
  and `latest` to the public Docker Hub repository.
- Inspect the VPS operating system and resources before mutation.
- On supported Ubuntu or Debian, install Docker Engine, Buildx, and the Docker
  Compose plugin from Docker's official APT repository.
- Install and configure host Nginx as a reverse proxy to
  `127.0.0.1:8000`.
- Run the agent and Redis under `/opt/day12-agent` with restart policies.
- Configure firewall rules without locking out the current SSH connection.
- Wait for the user to create the required DNS record and verify public
  propagation.
- Install Certbot, obtain the certificate, redirect HTTP to HTTPS, and test
  automatic renewal.
- Run remote endpoint, authentication, Redis-backed rate-limit, and TLS checks.
- Update submission documentation and evidence with verified results.

### Excluded

- Changing the domain registrar or DNS provider account directly.
- Disabling root/password SSH during deployment. That hardening needs a tested
  alternative administrator key first and is not required for this lab.
- Storing Docker Hub credentials on the VPS, because the selected image is
  public.
- Using the disclosed SSH password as an application secret.
- Adding a live OpenAI key; the mock LLM remains the deployed backend.
- Removing unrelated repository files or user changes.

## Image Build and Registry Flow

The image will target `linux/amd64`, matching the expected VPS architecture.
Before pushing, the container will be checked for non-root execution, health,
readiness, authentication, and absence of the local `.env` file.

Two tags will be published:

- An immutable `huygoodboy/day12-agent` tag whose value is the first 12
  hexadecimal characters of the exact Git commit being built, for deployment
  and rollback.
- `huygoodboy/day12-agent:latest` for the documented default pull command.

The VPS Compose file will pin the immutable tag used by the verified release.
Updating `latest` alone will not silently change the running deployment.

## VPS Files and Runtime

The deployment directory is `/opt/day12-agent` and contains:

- `docker-compose.yml`, safe to version and copy.
- `.env`, generated on the VPS with mode `0600` and never committed.
- Operational backups of any pre-existing Nginx site file changed by the task.

Compose runs an `agent` service and a `redis` service. The agent binds only
`127.0.0.1:8000:8000`; Redis has no published host port. Both services use
`restart: unless-stopped`. Redis uses a named volume and an internal health
check. The agent waits for Redis readiness and uses the service URL
`redis://redis:6379/0`.

The VPS `.env` receives independently generated values for `AGENT_API_KEY` and
`JWT_SECRET`, with `ENVIRONMENT=production`, `DEBUG=false`,
`RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=5.0`, and the allowed HTTPS
origin. Secret values are used for verification but are never printed, captured,
or added to documentation.

## Host Provisioning and Safety

The first SSH session performs read-only inventory: `/etc/os-release`, CPU
architecture, free disk and memory, listening ports, firewall status, and
installed packages. The Docker installation proceeds only for a supported
Ubuntu or Debian release. Any other distribution pauses for a revised package
plan.

Docker is installed from the official repository rather than the convenience
script. Nginx is installed from the distribution repository. Firewall changes
first preserve the active SSH port, then allow ports 80 and 443. The Docker app
port remains loopback-only because Docker-published ports can bypass ordinary
UFW policy when bound publicly.

Remote commands are executed non-interactively with the provided SSH credential
held only in process memory. The credential is not saved in the workspace,
Docker image, VPS deployment directory, logs, or documentation. The user should
rotate the root password after successful deployment because it has been shared
in conversation.

## DNS and TLS Flow

After the HTTP deployment is healthy by IP, the user configures this DNS record:

| Field | Value |
|---|---|
| Type | `A` |
| Name/Host | `day12` |
| IPv4 value | `103.77.241.150` |
| TTL | `300` or provider `Auto` |

An `AAAA` record for `day12` must be removed unless the VPS has verified IPv6.
If the DNS provider is Cloudflare, the record remains DNS-only until certificate
issuance succeeds.

Provisioning pauses until independent DNS resolution returns the target IPv4
address and the Nginx HTTP virtual host responds on port 80. Certbot then uses
the Nginx plugin, the supplied registration email, agreement to the Let's
Encrypt terms, non-interactive mode, and HTTP-to-HTTPS redirect. A successful
`certbot renew --dry-run` is required before completion.

## Nginx Behavior

Nginx routes `day12.huygoodboy.io.vn` to the loopback application port. It
forwards the original host, client address, forwarded-for chain, and scheme;
uses practical proxy timeouts; and rejects requests for unrelated hostnames
through the normal default-site behavior. Certbot may add the managed TLS server
block and redirect after the HTTP configuration passes validation.

## Verification and Acceptance Criteria

The deployment is complete only when all checks pass:

1. Python compilation and the production-readiness checker pass locally.
2. The local image builds for `linux/amd64` and runs as a non-root user.
3. Docker Hub exposes both the immutable tag and `latest` under the selected
   repository.
4. The VPS reports supported OS/architecture and a running Docker Engine plus
   Compose plugin.
5. `docker compose pull` obtains the published image on the VPS.
6. Agent and Redis containers are healthy and configured to restart.
7. Redis and port 8000 are not publicly reachable; Nginx serves port 80/443.
8. DNS resolves `day12.huygoodboy.io.vn` to `103.77.241.150`.
9. HTTPS presents a valid certificate for the hostname and HTTP redirects to
   HTTPS.
10. `/health` and `/ready` return 200 over HTTPS.
11. `/ask` returns 401 without a key and 200 with the deployed key.
12. JWT issuance/verification and authenticated `/metrics` return 200.
13. A controlled request burst produces HTTP 429, demonstrating Redis-backed
    shared rate limiting.
14. `certbot renew --dry-run` succeeds.
15. Git tracks no live secret, and documentation contains only safe commands and
    the verified public URL.

## Failure Handling and Rollback

- If the local build fails, no registry or VPS mutation occurs.
- If Docker Hub push fails, VPS provisioning may continue only through Docker
  installation; application deployment waits for a verified image tag.
- If VPS inventory identifies an unsupported OS, package installation stops.
- If a package or configuration step fails, the failing service logs and config
  validation are inspected before retrying; destructive blanket cleanup is not
  used.
- Nginx configuration must pass `nginx -t` before reload. Any existing changed
  site file is backed up first.
- If DNS is not correct, Certbot is not run and the working HTTP deployment is
  preserved.
- If the new application tag is unhealthy, Compose is returned to the previous
  immutable image tag and restarted.
- If Certbot fails, Nginx remains on validated HTTP configuration while DNS and
  firewall causes are corrected.

## Documentation Outcome

The final repository will document the Docker Hub image, immutable deployed tag,
VPS platform, public HTTPS URL, safe redeployment and rollback commands, DNS
record, certificate renewal check, and observed endpoint results. Earlier
Railway planning files remain historical records but are explicitly superseded
by this VPS design for the current deployment.
