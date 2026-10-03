# Development

Use Python 3.14 and one of the tested HA versions. Tests use real isolated HA, invented device names and fake HTTP responses. No live account is required and no real household is contacted.

```sh
python3.14 -m venv .venv
.venv/bin/pip install homeassistant==2026.9.4 -r requirements-dev.txt -r requirements-conversation-2026.9.4.txt
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
.venv/bin/python -m pytest -q
```

CI runs 2026.8.1 and 2026.9.4 plus HACS and hassfest validation. Provider tests keep real TypeSafe SDK serialization/parsing while replacing only the HTTP transport. Lifecycle tests install the config entry and entity, call HA conversation processing and actual local light services, and unload/reload/remove the entry.

The companion Phoenix repository also checks both integrations together over a real isolated TLS connector and Gateway turn. See its CONTRIBUTING.md and set JEV_PROJECT_DIR to this repository when running those tests.

Make a flat release asset containing the files from custom_components/jev_assist, with manifest.json at the zip root. HACS installs it inside that domain's directory. Never include tests, keys, .storage, caches, robot captures or operator notes in the archive. Use a new version and immutable tag for every release.

HACS CI excludes brands (no catalogue icon submission) and the action-only license check because upstream declares no source license. See UPSTREAM.md. Runtime/custom-repository structure and manifest checks remain enabled; this fork is not submitted to the default catalogue.
