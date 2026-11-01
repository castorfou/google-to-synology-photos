# Developer guide

`g2s` is a Python 3.12 command-line tool that turns a Google Takeout Export into a NAS Library in Synology Photos. It has no state of its own: each run works from the exports and from what the NAS holds.

The vocabulary (Album, Caption, Refresh and so on) is defined in `CONTEXT.md` at the repository root. Commands, conventions and the workflow are in `CLAUDE.md`.

## Where to find what

| Topic | Page |
|---|---|
| Modules | [Architecture: Modules](architecture.md#modules) |
| Identity rules (photo `url`, content hash, Album by photos) | [Architecture: Identity](architecture.md#identity) |
| The path rule | [Architecture: NAS path rule](architecture.md#nas-path-rule) |
| The run order, and Refresh | [Architecture: Order of a run](architecture.md#order-of-a-run) |
| The API calls and their quirks | [Synology Photos API](synology-photos-api.md) |
| The tests and the fake Synology Photos | [Architecture: Tests](architecture.md#tests) |
| The opt-in contract test | [Synology Photos API: Contract test](synology-photos-api.md#contract-test) |

Read [Synology Photos API](synology-photos-api.md) before changing `dsm.py` or `synology_client.py`.

## Working on the code

```bash
uv sync --active --all-extras     # dependencies
uv run --active pytest            # tests; needs ffmpeg and ExifTool
uv run --active mkdocs build --strict
pre-commit run --all-files
```

The repository is public. Tests, fixtures and docs hold no personal data, and the real exports stay in `data/raw/`, which git ignores.

{% include "../bonnes_pratiques.md" %}
