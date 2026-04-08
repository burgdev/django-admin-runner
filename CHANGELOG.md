# Changelog

## [0.1.0] - 2026-04-08

### Features

- Initial release
- `@register_command` decorator with `group`, `permission`, `params`, `exclude_params`, and `models` support
- Auto-generated forms from argparse introspection
- Pluggable task runners: `SyncCommandRunner`, `DjangoTaskRunner`, `CeleryCommandRunner`
- `CommandRunnerModelAdminMixin` for attaching run links to model admin pages
- Plain Django admin and Unfold admin support
- `CommandExecution` model with full audit trail
