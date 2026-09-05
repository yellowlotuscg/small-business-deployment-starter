# Support handoff

## Before starting

Use synthetic data only. Record the app version and who owns support. The app
has no login or production hardening. Bind local access to loopback.

## Local operation

```sh
python3 -m unittest discover -s tests -v
python3 -m app.seed
python3 -m app.server
```

In another terminal, inspect `http://127.0.0.1:8080/health` and `/api/summary`.
A healthy result proves the local health check, not external availability or
backup freshness. File-backed mode does not prove the volume survives replacement.

## Backup and recovery

Use `bash scripts/backup.sh` for an additive SQLite online backup. Test a restore
in an isolated scratch copy, with the app stopped, using `scripts/restore.sh`.
Do not overwrite the live database while a server still holds its connection.
The restore helper refuses an existing target without explicit `--force`.
Keep source backups separate from the test data, check the restored records,
and record the result before calling recovery verified.

## Release and rollback

`bash scripts/release.sh 1.0.0` runs tests and snapshots source. The rollback
script changes the release pointer only. An operator must separately select
that snapshot as the working directory and restart the service safely. Neither
script rolls database changes back or deploys a cloud image.

## Troubleshooting

- Connection refused: check the process, selected port and host binding.
- Missing data after restart: check mode and storage lifecycle. In-memory data
  loss is expected for the disposable demo.
- Invalid order: check stock and input values before retrying.
- Failed restore: preserve the original file and inspect integrity and target
  existence. Do not bypass the no-clobber gate blindly.

Cloud references describe prerequisites and limitations, not a live service.
