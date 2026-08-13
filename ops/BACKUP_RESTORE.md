# Backup and restore

## Backup

Run `./ops/scripts/backup.sh` before every schema or runtime change. Backups go
to `~/Atemoya/backups/<UTC timestamp>` by default, outside Git, with private
permissions. A backup includes a PostgreSQL custom dump and workflow JSON. It
does not export n8n credentials, plaintext API tokens, passwords, 2FA codes or
private keys. Keep the existing `N8N_ENCRYPTION_KEY` separately in the Owner's
password manager.

## Restore drill

Do not test restoration over production. Create an isolated PostgreSQL 16
container and restore the selected dump with `pg_restore --clean --if-exists`
only inside that isolated container. Verify row counts and n8n startup, then
delete the drill container. A production restore requires Owner approval,
confirmed backup path, downtime window and rollback plan.

Workflow JSON can be imported from the backup directory through the n8n CLI or
UI. Import does not include credentials; map references to the preserved live
credentials and keep imported workflows inactive until reviewed.
