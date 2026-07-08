# External Scheduler

GitHub scheduled workflows did not produce `schedule` runs reliably for this repository, even with a minimal probe workflow. The primary production trigger is now an external scheduler that calls the `workflow_dispatch` API for the existing `Weather Agent` workflow.

The GitHub cron entry in `.github/workflows/weather-agent.yml` is kept only as a fallback. It is not the primary production scheduler.

## Workflow Dispatch Endpoint

Repository:

```text
dili1324/weather-agent-06x0dean
```

Workflow file:

```text
.github/workflows/weather-agent.yml
```

GitHub REST endpoint:

```text
POST https://api.github.com/repos/dili1324/weather-agent-06x0dean/actions/workflows/weather-agent.yml/dispatches
```

Request body:

```json
{
  "ref": "main"
}
```

GitHub documents this endpoint as "Create a workflow dispatch event". The `workflow_id` path value can be the workflow file name, and the request body must include `ref`.

## GitHub Token

Create a fine-grained personal access token for the repository `dili1324/weather-agent-06x0dean`.

Required repository permission:

```text
Actions: Read and write
```

If GitHub shows separate wording, choose the option that grants write access to Actions. Do not grant broader permissions unless the scheduler provider cannot work without them.

## Curl Example

Use this command only for local/manual validation. Do not commit the token.

```bash
GITHUB_TOKEN="github_pat_xxx"

curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  https://api.github.com/repos/dili1324/weather-agent-06x0dean/actions/workflows/weather-agent.yml/dispatches \
  -d '{"ref":"main"}'
```

Expected result:

```text
Any HTTP 2xx success response.
```

Recent GitHub REST documentation describes a `200` response with workflow run details. Older examples and clients may show `204 No Content`. Treat either as success, then open GitHub Actions and confirm a new `Weather Agent` run appears with event `workflow_dispatch`.

## cron-job.org Setup

Create a new cron-job.org job:

```text
URL: https://api.github.com/repos/dili1324/weather-agent-06x0dean/actions/workflows/weather-agent.yml/dispatches
Method: POST
Timezone: Asia/Ho_Chi_Minh
Schedule: Every day at 06:50
```

Headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer <GITHUB_FINE_GRAINED_PAT>
X-GitHub-Api-Version: 2026-03-10
Content-Type: application/json
```

Body:

```json
{"ref":"main"}
```

After saving the job, run it manually once from cron-job.org and verify:

1. cron-job.org reports an HTTP success response.
2. GitHub Actions shows a new `Weather Agent` run.
3. Telegram receives the weather report.

## Security Notes

- Never commit the GitHub token.
- Store the token only in the external scheduler's secret/header configuration.
- Use a fine-grained PAT scoped only to `dili1324/weather-agent-06x0dean`.
- Grant only `Actions: Read and write`.
- Rotate the token if the scheduler account or token might be exposed.
- Keep using the existing GitHub repository secrets for Telegram and Tempo wallet state. Do not move Tempo wallet store data into the external scheduler.
- Do not place Telegram tokens, Tempo wallet state, or GitHub PAT values in URLs because URLs are commonly logged.
