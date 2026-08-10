# Day 12 Railway Free Deployment Plan

## Goal

Deploy `06-lab-complete` to Railway Free with a public URL and a private
Redis-compatible service, then make the repository documentation and evidence
match the verified deployment.

## Constraints

- Use Railway Free only.
- Never accept an upgrade, payment method request, paid plan, or paid add-on.
- Never commit or print live secrets.
- Preserve the student's uncommitted checklist information.
- Deploy only `06-lab-complete` from the monorepo.

## Work Sequence

1. Reconcile the working Dockerfile into a multi-stage, non-root image whose
   runtime command listens on Railway's `PORT` with a local default of 8000.
2. Restore `06-lab-complete/railway.toml` with Dockerfile build, `/health`, a
   restart policy, and a `$PORT`-aware start command.
3. Strengthen `smoke_test.py` so authenticated tests use an explicitly supplied
   environment key when available and the rate-limit test asserts at least one
   HTTP 429 instead of accepting arbitrary statuses.
4. Run compilation, the readiness checker, secret scanning, diff checks, and
   local endpoint tests that do not require Docker.
5. Commit the code/configuration changes and push them to `origin/main`.
6. Use the authenticated Railway CLI to create or link a Free project, create
   the web service and Redis-compatible service, and set production variables.
7. Generate strong application secrets in process memory and inject them into
   Railway without placing them in command output, files, or documentation.
8. Deploy `06-lab-complete`, wait for a healthy deployment, and create a public
   domain.
9. Verify `/health`, `/ready`, 401/200 authentication behavior, JWT, metrics,
   and an asserted 429 response against the public URL.
10. Capture non-secret evidence from the real deployment, update submission
    documentation and checklist claims, then commit and push the final state.

## Stop Conditions

- Railway requests a paid upgrade or billing action.
- Railway Free does not permit the required web or Redis-compatible service.
- Authentication or permission errors require user interaction.
- A requested external mutation would expose or repurpose a credential.

## Acceptance

- Static readiness is 20/20.
- Railway reports a successful deployment on Free.
- The public health endpoint returns HTTP 200.
- All remote behavioral checks pass, including rate-limit 429.
- Documentation contains the real URL and no false completion claims.
- No secret is tracked by Git.
- `origin/main` contains the final reviewed commits.
