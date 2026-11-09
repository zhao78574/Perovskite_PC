# Perovskite_PC Instructions

## Scope

- Work only on files directly related to the user's request.
- Before editing, identify the smallest set of source files, callers, and tests involved.
- Preserve unrelated working-tree changes. Do not reformat or refactor unrelated code.
- Prefer existing project patterns and the smallest complete change. Do not add dependencies unless explicitly approved.

## Context And Token Use

- Do not recursively list or inspect the whole repository.
- Keep searches path-scoped and file-type-scoped. Keep command output concise.
- Never read, search, summarize, or include generated or dependency content from:
  - `.git/`
  - `.venv/` and `.venv-*/`
  - `__pycache__/` and `.pytest_cache/`
  - `archive/`
  - `build/` and `dist/`
  - `node_modules/`
  - `packaging/release-build*/`
  - `packaging/release-dist*/`
- Treat generated PNG, PDF, SVG, EXE, DLL, ZIP, and build logs as outputs. Inspect them only when the request specifically concerns them.
- If the same command or environment error occurs twice, stop and report it. Do not repeatedly try browsers, tool searches, or alternative shells.

## Project Layout

- `build_exe.py`: Python desktop backend and packaging entry point.
- `src/index.html`: main application interface and browser-side logic.
- `analysis/`: scientific analysis scripts; preserve numerical behavior and calibration.
- `tests/`: JavaScript tests.
- `assets/`: application icons and images.
- `XPS_Output/`: keep Python source; image, PDF, and SVG files are generated outputs.

## Validation

- Run only the smallest test directly related to the change.
- Do not run a full PyInstaller build, generate an EXE, install dependencies, or run all tests unless explicitly requested.
- For changes to scientific calculations, preserve units and existing numerical tolerances and add or update one focused test.
- Report the files changed, the focused test result, and any remaining risk. Do not paste large files, full logs, or large diffs.

## Safety

- Do not delete files, stop processes, reset Git, commit, push, publish, or overwrite user changes without explicit approval.
- Ask before changing release, signing, update, certificate, or installer configuration.
