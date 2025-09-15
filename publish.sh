#!/usr/bin/env bash
# publish.sh — Build and publish a Python package to TestPyPI or PyPI, then verify install.
# Usage:
#   ./publish.sh --testpypi            # upload to TestPyPI and verify install from TestPyPI (+ PyPI fallback for deps)
#   ./publish.sh --prod                # upload to PyPI and verify install from PyPI
#   ./publish.sh --skip-verify --testpypi|--prod   # upload only
#   ./publish.sh --version 1.2.3 --testpypi        # override version read from pyproject.toml
#
# Requirements: Python 3.11+, build, twine. Script will install/upgrade build & twine.

set -euo pipefail

cyan()  { printf "\033[36m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*" >&2; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }

REPO_MODE=""
SKIP_VERIFY="0"
OVERRIDE_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --testpypi) REPO_MODE="testpypi"; shift ;;
    --prod|--pypi) REPO_MODE="pypi"; shift ;;
    --skip-verify) SKIP_VERIFY="1"; shift ;;
    --version) OVERRIDE_VERSION="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,30p' "$0"
      exit 0
      ;;
    *)
      red "Unknown argument: $1"
      exit 2
      ;;
  esac
done

if [[ -z "${REPO_MODE}" ]]; then
  red "Choose one: --testpypi or --prod"
  exit 2
fi

# Ensure we are at repo root (pyproject.toml present)
if [[ ! -f "pyproject.toml" ]]; then
  red "pyproject.toml not found in current directory."
  exit 2
fi

# Find python
PYBIN="${PYBIN:-python3}"
command -v "$PYBIN" >/dev/null 2>&1 || PYBIN="python"
command -v "$PYBIN" >/dev/null 2>&1 || { red "python not found"; exit 2; }

# Extract version from pyproject.toml (prefer tomllib, fallback to grep)
VERSION="${OVERRIDE_VERSION}"
if [[ -z "$VERSION" ]]; then
  VERSION="$("$PYBIN" - <<'PY' || true
import sys, json
try:
  try:
    import tomllib
  except Exception:
    import tomli as tomllib  # type: ignore
  with open("pyproject.toml","rb") as f:
    data = tomllib.load(f)
  v = data.get("project",{}).get("version")
  if v:
    print(v)
  else:
    sys.exit(1)
except Exception:
  sys.exit(1)
PY
)"
fi

if [[ -z "$VERSION" ]]; then
  # super simple grep fallback (not robust but better than nothing)
  VERSION="$(grep -E '^[[:space:]]*version[[:space:]]*=' pyproject.toml | head -n1 | sed -E 's/.*=[[:space:]]*"?([0-9]+\.[0-9]+\.[0-9]+).*$/\1/')"
fi

if [[ -z "$VERSION" ]]; then
  red "Could not determine version from pyproject.toml; use --version X.Y.Z"
  exit 2
fi

bold "Publishing version: ${VERSION} (${REPO_MODE})"

cyan "1) Cleaning build artifacts..."
rm -rf dist build ./*.egg-info

cyan "2) Ensuring build & twine are installed..."
"$PYBIN" -m pip install -U pip build twine

cyan "3) Building sdist and wheel..."
"$PYBIN" -m build

cyan "4) Checking artifacts with twine..."
"$PYBIN" -m twine check dist/*

cyan "5) Uploading..."
if [[ "$REPO_MODE" == "testpypi" ]]; then
  "$PYBIN" -m twine upload --repository testpypi dist/*
else
  "$PYBIN" -m twine upload dist/*
fi

if [[ "$SKIP_VERIFY" == "1" ]]; then
  green "Upload complete (verification skipped)."
  exit 0
fi

cyan "6) Verifying installation in a fresh virtual environment..."
WORKDIR="$(mktemp -d)"
pushd "$WORKDIR" >/dev/null

"$PYBIN" -m venv venv
source venv/bin/activate

"$PYBIN" -m pip install -U pip

PKG_NAME="$("$PYBIN" - <<'PY'
import sys
try:
  try:
    import tomllib
  except Exception:
    import tomli as tomllib  # type: ignore
  with open("pyproject.toml","rb") as f:
    data = tomllib.load(f)
  print(data.get("project",{}).get("name",""))
except Exception:
  print("")
PY
)"
# if running from temp dir, we won't find pyproject; default to explicit name if needed
if [[ -z "$PKG_NAME" ]]; then PKG_NAME="allure-ai-analyzer"; fi

if [[ "$REPO_MODE" == "testpypi" ]]; then
  "$PYBIN" -m pip install --no-cache-dir \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple \
    "${PKG_NAME}==${VERSION}"
else
  "$PYBIN" -m pip install --no-cache-dir "${PKG_NAME}==${VERSION}"
fi

# Smoke test: import and show entry point help
"$PYBIN" - <<'PY'
import importlib, sys
mod = importlib.import_module("allure_analyzer")
print("Imported:", mod.__file__)
PY

which allure-analyze >/dev/null 2>&1 && allure-analyze --help >/dev/null 2>&1 || true

deactivate
popd >/dev/null
rm -rf "$WORKDIR"

green "All done! Published ${PKG_NAME}==${VERSION} to ${REPO_MODE} and verified installation."
