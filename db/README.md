# PostgreSQL operational memory

Run migrations only after a verified backup:

```sh
./ops/scripts/backup.sh
./ops/scripts/apply-migrations.sh
./ops/scripts/verify.sh
```

Migrations are additive and idempotent. They never drop tables, columns, data,
roles, or extensions. Existing n8n tables remain untouched.
