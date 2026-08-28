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
- `PORT_MONITOR_STATUS_PATH=/app/logs/Major US Port Data Monitor.status.json`
- `PORT_MONITOR_STATUS_URL=`
- `PORT_MONITOR_STATUS_TOKEN=<shared-status-token>`
- `DASHBOARD_ZOOM_WEBHOOK_URL=<zoom-incoming-webhook-endpoint>`
- `DASHBOARD_ZOOM_WEBHOOK_TOKEN=<zoom-verification-token>`
- `DASHBOARD_ZOOM_DEDUPE_SECONDS=1800`
- `SUPABASE_URL=https://your-project.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
- `SUPABASE_USAGE_SNAPSHOT_TABLE=api_usage_stats_snapshot`
- `USAGE_STATS_CACHE_SECONDS=86400`

Notes:

- `DASHBOARD_LOG_PATH` should be an absolute path on the Docker host running Portainer.
- `PORT_MONITOR_STATUS_PATH` should point to the port monitor JSON status file inside the container. The default expects the file to be present in the mounted dashboard log directory.
- `PORT_MONITOR_STATUS_URL` can point to an internal URL serving the JSON. If set, it takes precedence over `PORT_MONITOR_STATUS_PATH`.
- `PORT_MONITOR_STATUS_TOKEN` is required if the port monitor POSTs status updates to `/api/port_data_status`.
- `DASHBOARD_ZOOM_WEBHOOK_URL` and `DASHBOARD_ZOOM_WEBHOOK_TOKEN` enable low-detail Zoom Workplace Chat failure alerts.
- `DASHBOARD_ZOOM_DEDUPE_SECONDS` suppresses repeated alerts for the same component and reason.
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
   - `PORT_MONITOR_STATUS_PATH=/app/logs/Major US Port Data Monitor.status.json`
   - `PORT_MONITOR_STATUS_URL=`
   - `PORT_MONITOR_STATUS_TOKEN=<shared-status-token>`
   - `DASHBOARD_ZOOM_WEBHOOK_URL=<zoom-incoming-webhook-endpoint>`
   - `DASHBOARD_ZOOM_WEBHOOK_TOKEN=<zoom-verification-token>`
   - `DASHBOARD_ZOOM_DEDUPE_SECONDS=1800`
   - `SUPABASE_URL=https://your-project.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
   - `SUPABASE_USAGE_SNAPSHOT_TABLE=api_usage_stats_snapshot`
   - `USAGE_STATS_CACHE_SECONDS=86400`
8. Deploy the stack.
9. After the container starts, open `http://<your-server>:5005/health` and confirm it returns a healthy response.
10. Open `http://<your-server>:5005/ports` and confirm the port status table loads.

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

### Port data status says the status file is missing

If `/ports` says the port monitor status file is missing, confirm the daily port monitor is writing `Major US Port Data Monitor.status.json` and that the file is available inside the container at `PORT_MONITOR_STATUS_PATH`.

For the default compose settings, copy or sync the JSON into the host directory configured by `DASHBOARD_LOG_PATH`, which appears in the container as `/app/logs`. As an alternative, serve the JSON internally and set `PORT_MONITOR_STATUS_URL`.

When the dashboard is hosted on a different machine than the port monitor, set `status_publish_url` in the port monitor config to `http://<dashboard-host>:5005/api/port_data_status` and set the same `PORT_MONITOR_STATUS_TOKEN` in both environments. The dashboard stores posted updates at `PORT_MONITOR_STATUS_PATH`.

### Zoom alerts do not appear

Confirm the dashboard container has `DASHBOARD_ZOOM_WEBHOOK_URL` and `DASHBOARD_ZOOM_WEBHOOK_TOKEN` set. `/health` reports `zoom_notifications` as `configured` when both values are visible to the app.

Alerts are intentionally low-detail and deduped by component and reason for `DASHBOARD_ZOOM_DEDUPE_SECONDS`, which defaults to 1800 seconds.

To send live test alerts after deployment, POST to `/api/zoom_alert_test/<component>` with `X-Automation-Operator-Token`. Supported components are `api_testing`, `folder_monitor`, `ftp_transfer`, `usage_stats`, `port_data_monitor`, and `automation_status`.

## Quick Verification

Before you rely on auto-updates, confirm:

- `docker-compose.yml` uses the exact same GHCR path the workflow publishes
- the workflow has produced a `latest` tag
- Portainer can pull the image
- `/health` responds successfully after deployment
- `/health` reports `zoom_notifications` as `configured` if Zoom alerts are expected
- `/ports` returns the port data status page
- `/api/port_data_status` returns the generated port monitor JSON
- Watchtower is running in the stack
