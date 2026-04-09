# Example: Classic

Plain Django admin with synchronous command execution via Django's built-in
`ImmediateBackend`. No worker process or broker needed.

## Setup & run

```bash
cd examples/classic
make init   # install deps, migrate, create superuser (root/root)
make run    # start dev server on port 8765
```

Visit <http://localhost:8765/admin/> (login: `root` / `root`) and navigate to
**Admin Runner → Run Management Commands** to execute the example commands.

## What's included

- `books` app with three example commands:
  - **Import Books** (`import_books`) — simulates a CSV import with `--source`,
    `--dry-run`, and `--limit` arguments
  - **Cleanup Books** (`cleanup_books`) — removes stale records; `--verbosity`
    excluded from the run form via `exclude_params`
  - **Export Report** (`export_report`) — exports in CSV/JSON/XLSX format via a
    choice field; `--output-path` hidden from the form via `hidden=True`

## Available `make` targets

```
make          # show this help
make init     # install deps, migrate, create superuser
make run      # start Django dev server on port 8765
```
