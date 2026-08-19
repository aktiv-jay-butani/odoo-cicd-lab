# odoo-cicd-lab

Odoo 19 CI/CD pipeline — mirrors what odoo.sh does on merge-to-staging:
build → fresh install with tests → build image → deploy.

## Flow

1. Push/merge to `dev` → `.github/workflows/merge.yml` fast-forward-merges
   `dev` into `staging` and pushes.
2. That push to `staging` triggers `.github/workflows/staging-build-test-deploy.yml`:
   - **build-and-test**: builds a Docker image with your addons baked in
     (`docker/Dockerfile`), spins up a throwaway Postgres, does a fresh
     `-i <all custom modules> --test-enable`, and fails the whole job if
     the log shows any `ERROR`, `CRITICAL`, traceback, or test `FAILED`
     line (`scripts/run_tests.sh`). The full log is uploaded as a build
     artifact either way.
   - **deploy** (only runs if tests passed): pushes the image to GHCR,
     SSHes into the staging server, pulls the new image, brings the
     stack up, and runs `-u all` against the real staging database.

## Repo layout expected

```
addons/                 one folder per custom module
requirements.txt        extra python deps your addons need
docker/Dockerfile        builds the deployable image
scripts/run_tests.sh     install + test + fail-on-error logic
```

## One-time setup

- Copy `docker/docker-compose.staging.yml.example` to
  `/opt/odoo-staging/docker-compose.yml` on the staging server, set a
  `POSTGRES_PASSWORD` in a `.env` next to it, and `docker compose up -d`
  once manually to seed the `staging` database.
- Add these repo secrets (Settings → Secrets and variables → Actions):
  | Secret | Purpose |
  |---|---|
  | `STAGING_SSH_HOST` | staging server address |
  | `STAGING_SSH_USER` | SSH user with docker access |
  | `STAGING_SSH_KEY`  | private key for that user |
  `GITHUB_TOKEN` is automatic — used to push/pull the image from GHCR.
- Make sure the GHCR package is set to be readable by the staging
  server's login (or make it public) — Package settings → Manage Actions access.

## GitHub-hosted vs self-hosted runner

Start with GitHub-hosted (`ubuntu-latest`) — for a handful of custom
modules this comfortably finishes within its 2 CPU / 7GB RAM. Move to
a self-hosted runner once any of these happen:
- module count/test suite makes the job regularly exceed ~15–20 min
- the staging server isn't reachable from the public internet (self-hosted
  runner living on your own network sidesteps needing SSH exposed)
- you want to cache the Postgres/pip layers between runs for speed

## Extending toward full odoo.sh parity

- **Per-PR ephemeral builds**: duplicate `staging-build-test-deploy.yml`
  triggered `on: pull_request` targeting `dev`, skip the deploy job,
  and post the test log as a PR comment.
- **JS/tour tests**: add `--test-tags=/module,at_install,post_install`
  and install a headless browser in the Dockerfile (Odoo's HttpCase
  tours need Chrome headless) if you use browser tour tests.
- **Coverage**: wrap the odoo-bin call in `coverage run` and upload an
  HTML report as a build artifact.
- **DB dump/restore for staging**: odoo.sh seeds each build from a
  neutralized production dump. You can replicate this by having the
  deploy step `pg_restore` a nightly-refreshed staging dump before
  running `-u all`, instead of reusing whatever's already in `staging`.
