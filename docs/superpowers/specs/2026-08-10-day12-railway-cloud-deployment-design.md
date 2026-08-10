# Day 12 Railway Cloud Deployment Design

## Context

The repository already contains a production-oriented FastAPI agent in
`06-lab-complete`, including API-key authentication, JWT authentication, Redis
rate limiting, a Redis-backed cost guard, health and readiness endpoints,
Docker Compose files, load-balancing examples, smoke tests, and submission
documentation.

The current `main` branch is synchronized with `origin/main`, but the working
tree has three uncommitted changes: a Dockerfile modification, deletion of
`06-lab-complete/railway.toml`, and student information added to the delivery
checklist. These changes must be reconciled without discarding the student's
work.

The latest diagnostic results are:

- Python source compilation passes.
- The production-readiness checker reports 19/20 because the modified
  Dockerfile runs as root.
- The modified Dockerfile does not explicitly bind Uvicorn to Railway's
  injected `PORT`.
- `railway.toml` is deleted locally while the submission documents still say
  it exists.
- The repository contains local verification screenshots but no public
  deployment URL.
- Several documents claim 20/20 readiness and completed deployment despite the
  current repository state.
- Railway CLI 5.35.0 is installed and authenticated as the student's account,
  but the repository is not linked to a Railway project.

## Objective

Deploy the `06-lab-complete` application to Railway with a public domain and a
Redis-compatible backing service, verify the required behavior against the
public URL, and update the repository so its code, evidence, and documentation
truthfully describe the deployed system.

The deployment must not commit, print, or otherwise expose real credentials.
No paid Railway upgrade will be initiated without explicit user approval.

## Scope

### Included

- Reconcile and harden the production Dockerfile.
- Restore a valid Railway configuration for the isolated project directory.
- Create or link a Railway project and web service.
- Provision a Railway Redis-compatible service and connect it through
  `REDIS_URL`.
- Generate strong application secrets locally and inject them through Railway
  environment variables.
- Create a public Railway domain.
- Run local/static checks and remote behavioral checks.
- Capture evidence from the real public service.
- Update `README.md`, `DEPLOYMENT.md`, `MISSION_ANSWERS.md`, and the delivery
  checklist to match verified facts.
- Commit and push the resulting deployment-ready repository.

### Excluded

- Enabling paid Railway plans or paid add-ons.
- Committing `.env` or any live API key, JWT secret, Redis credential, or
  Railway token.
- Integrating a live OpenAI model. The supplied mock LLM is sufficient for the
  deployment lab and avoids sharing an OpenAI key with the cloud service.
- Refactoring unrelated lab sections.
- Deploying the Nginx three-replica demonstration stack as the public service.
  The public deployment will use one stateless web service backed by Redis;
  horizontal scaling remains demonstrated by the existing lab artifacts.

## Chosen Approach

Use Railway CLI to deploy `06-lab-complete` as an isolated service from the
monorepo. Railway is selected because its CLI is already installed and
authenticated, the lab explicitly targets Railway, and the workflow can create
the service, variables, Redis dependency, and domain with less manual dashboard
work than Render.

Render remains a documented alternative. A web-only Railway deployment without
Redis is not acceptable as the final result because it would weaken the
stateless rate-limit and cost-tracking requirements.

## Architecture

```text
Public client
    |
    | HTTPS
    v
Railway public domain
    |
    v
FastAPI web service (Docker, non-root)
    |-- /health and /ready
    |-- API-key and JWT validation
    |-- mock LLM response generation
    |
    +---- private REDIS_URL ----> Railway Redis-compatible service
                                 |-- sliding-window rate limits
                                 `-- monthly cost counters
```

The application remains stateless at the web-service layer. Railway injects
`PORT`; the service process binds to `0.0.0.0:$PORT`. Health checks use
`/health`, while `/ready` remains available for readiness verification.

## Repository Changes

### Dockerfile

The Dockerfile will retain a multi-stage build while restoring a dedicated
non-root runtime user. Runtime packages will be copied into a location readable
and executable by that user. The start command will support Railway's dynamic
port without breaking ordinary local Docker use. The health check will target
the same effective port and retain an adequate startup grace period.

The finished Dockerfile must pass the repository's static checks and build on
Railway. A local Docker build will also be run if the local Docker daemon becomes
available; otherwise Railway's successful image build is the authoritative
container-build result.

### Railway configuration

`06-lab-complete/railway.toml` will be restored as the config-as-code source for
the web service. It will select the Dockerfile build, configure `/health`, use a
bounded health-check timeout and restart policy, and run Uvicorn on `$PORT`.

Because this is an isolated project inside a monorepo, deployment will treat
`06-lab-complete` as the service root. The exact CLI form will be selected from
the installed Railway CLI's help output so that only this directory is uploaded
and the other lab directories are not built into the service.

### Application configuration

Production configuration will be provided with Railway variables:

- `ENVIRONMENT=production`
- `DEBUG=false`
- `AGENT_API_KEY`: a cryptographically generated 32-byte URL-safe value,
  created immediately before Railway variable injection and never stored in a
  tracked file
- `JWT_SECRET`: a separate cryptographically generated value of at least 32
  bytes, created and injected under the same handling rules
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=5.0`
- `ALLOWED_ORIGINS=*` for this API-only educational deployment
- `REDIS_URL`: Railway's private connection reference for the provisioned
  Redis-compatible service

`OPENAI_API_KEY` will remain unset so the deployed application uses the
repository's mock LLM. `PORT` will be supplied by Railway.

## Deployment Flow

1. Reconcile the existing Dockerfile changes and restore `railway.toml`.
2. Run source compilation, secret scanning, and the production-readiness
   checker.
3. Commit and push the code/configuration changes required for deployment.
4. Create and link a Railway project without upgrading the account plan.
5. Create the web service and Redis-compatible service.
6. Set production variables and connect `REDIS_URL` using Railway's private
   service reference.
7. Deploy only `06-lab-complete` and wait for a successful `/health` check.
8. Generate a Railway public domain.
9. Execute remote verification and collect non-secret evidence.
10. Update submission documents and screenshots with the real URL and verified
    results, then commit and push those artifacts.

If Railway reports that the available free/trial credit is insufficient or
requires a paid upgrade, deployment stops before accepting charges and the user
is asked to choose whether to authorize the cost or switch to Render Free.

## Data and Request Flow

For an authenticated `/ask` request, FastAPI validates `X-API-Key`, derives the
existing non-secret user bucket identifier, checks the Redis sliding-window
limit, checks and records estimated monthly cost, invokes the mock LLM, records
output cost, and returns the response. Missing or invalid keys return 401. More
than ten requests inside the configured minute window must eventually return
429. Budget exhaustion returns 402.

The Redis connection is private and is never exposed in documentation or test
output. Health checks do not depend on Redis, preventing a transient backing
service problem from blocking container startup. Rate limiting fails open and
cost tracking falls back to in-memory behavior when Redis is unavailable, as
implemented by the current lab code; remote verification will confirm that the
configured Redis service is reachable through observed rate-limit behavior.

## Security and Secret Handling

- Generate secrets with a cryptographically secure local mechanism.
- Pass generated values directly to Railway variables without writing them to
  tracked files or displaying them in commentary, logs, screenshots, or docs.
- Keep `.env` ignored and verify it is absent from Git history and the staged
  changes.
- Use a non-root runtime container user.
- Do not set `OPENAI_API_KEY` in Railway.
- Protect `/ask` and `/metrics`; keep `/health` and `/ready` public for platform
  probes.
- Review the final diff and staged file list before every commit.

## Verification and Acceptance Criteria

The deployment is complete only when all of the following are true:

1. `python -m compileall` succeeds for `app` and `utils`.
2. `check_production_ready.py` reports 20/20 in a UTF-8 terminal environment.
3. The Railway build and deployment complete successfully.
4. The public domain serves `GET /health` with HTTP 200.
5. `GET /ready` returns HTTP 200 after startup.
6. `POST /ask` without an API key returns HTTP 401.
7. `POST /ask` with the deployed API key returns HTTP 200 and a mock answer.
8. `POST /token` followed by `GET /secure` returns HTTP 200.
9. Authenticated `GET /metrics` returns HTTP 200.
10. A controlled burst against `/ask` produces HTTP 429 after the configured
    ten-request limit. The verification script must assert the 429 response,
    rather than count arbitrary responses as passes.
11. No live secret is tracked by Git or included in captured output.
12. Submission documentation contains the real public URL and does not claim
    checks that were not performed.
13. Evidence files show the real Railway deployment and public endpoint tests,
    rather than a simulated dashboard.
14. The final branch is pushed to `origin/main` with a clear, reviewable commit
    history.

## Error Handling and Recovery

- If the build fails, inspect Railway build logs, correct only the responsible
  Docker/config issue, and redeploy.
- If health checks fail, first confirm the process binds to Railway's `PORT`,
  then inspect application startup validation and service logs.
- If Redis cannot connect, verify the private reference and service region
  before changing application fallback behavior.
- If an external deployment operation would incur a charge, stop and request
  explicit approval.
- If the new deployment is unhealthy after a previous healthy deployment,
  Railway's failed health check should prevent promotion; otherwise redeploy the
  last known-good Git revision.
- Existing uncommitted student information in the checklist will be preserved.

## Documentation Outcome

After verification, the repository documentation will state one consistent
deployment status. The public URL, platform, environment-variable names, exact
test commands, observed status codes, and evidence filenames will agree across
`README.md`, `DEPLOYMENT.md`, `MISSION_ANSWERS.md`, and the delivery checklist.
No document will include the authentication key itself.
