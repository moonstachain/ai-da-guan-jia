# GitHub Project Schema

Use this as the baseline Project v2 schema for the central task board.

## Required Fields

- `Status`
- `Task Key`
- `Type`
- `Domain`
- `Verification`
- `Target Repo`
- `Run ID`
- `Archived At`

## Preferred Status Options

- `Inbox`
- `In Progress`
- `Waiting`
- `Verified`
- `Archived`

## Field Intent

- `Task Key`: stable cross-system identifier
- `Verification`: latest verification result from the local run
- `Target Repo`: central ops repo or target implementation repo
- `Archived At`: only set when the task is truly archived

## Implementation Note

If a field is missing in the live Project, skip that update and record the gap in `github-sync-result.json` instead of failing the whole sync.
