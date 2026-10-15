# Privacy

Agentic Verification collects no data.

- The `tsa` runner runs on your machine, against a copy of your project, and writes its reports to `.test-suite-audit/` inside that project.
- It sends nothing to the plugin's author or to any other service. The only network access is `uv` downloading the runner and its Python dependencies from GitHub and PyPI when the skill first runs.
- The skill's instructions run inside Claude, under your own Claude account and its data settings. The plugin adds no telemetry.

Questions: open an issue at https://github.com/timini/agentic-verification/issues.
