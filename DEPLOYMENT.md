# GHCR + Portainer + Watchtower Deployment

This repo is set up so GitHub Actions publishes a Docker image to GHCR, Portainer deploys the stack from `docker-compose.yml`, and Watchtower pulls new image versions automatically.

## What Gets Published

Workflow: `.github/workflows/docker-image.yml`

On every push to `main` or `master`, GitHub Actions publishes:

- `ghcr.io/actresearch/apidashboard:latest`
- `ghcr.io/actresearch/apidashboard:<branch>`
- `ghcr.io/actresearch/apidashboard:sha-<commit>`

`docker-compose.yml` is intentionally pointed at the `latest` tag, so Portainer + Watchtower always follow the newest image built from `main` or `master`.

## Required Portainer Environment Values

Set these in the Portainer stack editor or in a stack env file:

- `GHCR_IMAGE=ghcr.io/actresearch/apidashboard:latest`
- `APP_PORT=5005`
- `DASHBOARD_LOG_PATH=/opt/api-dashboard/logs`
- `SUPABASE_URL=https://your-project.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
- `SUPABASE_USAGE_SNAPSHOT_TABLE=api_usage_stats_snapshot`
- `USAGE_STATS_CACHE_SECONDS=86400`

Notes:

- `DASHBOARD_LOG_PATH` should be an absolute path on the Docker host running Portainer.
- `SUPABASE_SERVICE_ROLE_KEY` is a secret. Set it in Portainer; do not commit a real key to the repo.
- Portainer stack environment values are used for compose substitution. `docker-compose.yml` must also list a value under the service `environment:` block for it to appear inside the container.
- This app does not currently require Redis for the stack defined in this repo.

## Portainer Setup

1. Push this repo to GitHub.
2. Confirm the default branch is `main` or `master`.
3. Wait for the `Build and Push Docker Image` workflow to succeed.
4. In GitHub, open the published package under `Packages` and confirm the image path is exactly `ghcr.io/actresearch/apidashboard`.
5. In Portainer, create a new stack or edit the existing one.
6. Paste in `docker-compose.yml` from this repo, or deploy the stack from the Git repository if that is how your Portainer instance is configured.
7. Set the stack environment values:
   - `GHCR_IMAGE=ghcr.io/actresearch/apidashboard:latest`
   - `APP_PORT=5005`
   - `DASHBOARD_LOG_PATH=/opt/api-dashboard/logs`
   - `SUPABASE_URL=https://your-project.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
   - `SUPABASE_USAGE_SNAPSHOT_TABLE=api_usage_stats_snapshot`
   - `USAGE_STATS_CACHE_SECONDS=86400`
8. Deploy the stack.
9. After the container starts, open `http://<your-server>:5005/health` and confirm it returns a healthy response.

## Watchtower Behavior

The stack includes a dedicated `watchtower` service and the app container has the label:

- `com.centurylinklabs.watchtower.enable: "true"`

That means Watchtower only updates containers you explicitly label. It checks every 30 seconds in the current compose file and removes replaced images with `--cleanup`.

## GHCR Visibility and Authentication

GitHub repository visibility and GHCR package visibility are separate.

If your GitHub repo is public, the GHCR package can still be private. Portainer will only be able to pull private images if you configure registry credentials for `ghcr.io`.

If you want anonymous pulls, make the GHCR package public.

## Troubleshooting

### `unauthorized`

This usually means one of these is true:

- the GHCR package is private
- the credentials in Portainer are missing
- the credentials in Portainer do not have permission to read the package
- `GHCR_IMAGE` points to a different owner or package name than the one that was published

Check:

- package visibility in GitHub Packages
- Portainer registry credentials for `ghcr.io`
- the exact image path in `GHCR_IMAGE`

### `manifest unknown`

This usually means the tag Portainer is trying to pull does not exist yet.

Check:

- the workflow ran on `main` or `master`
- the workflow completed successfully
- the published image includes the `latest` tag
- `GHCR_IMAGE` exactly matches the published package path and tag

This repo's workflow is already configured to publish `latest` from both `main` and `master`, which avoids the usual missing-tag problem.

### Usage stats say Supabase environment variables are missing

If the dashboard says `Supabase environment variables are not configured`, inspect the `api-dashboard` container details in Portainer.

If `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are missing there, the values are defined in the Portainer stack but are not being injected into the service environment. Make sure `docker-compose.yml` includes them under `services.api-dashboard.environment`, then redeploy the stack.

## Quick Verification

Before you rely on auto-updates, confirm:

- `docker-compose.yml` uses the exact same GHCR path the workflow publishes
- the workflow has produced a `latest` tag
- Portainer can pull the image
- `/health` responds successfully after deployment
- Watchtower is running in the stack
