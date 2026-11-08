#!/usr/bin/env bash
# Samler websiden i _site/ (bruges af GitHub Actions og til lokal test).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _site && mkdir -p _site/femdoc _site/eksempler
cp web/index.html web/femdoc-loader.js _site/
cp femdoc/*.py _site/femdoc/
cp eksempel/struxml/*.struxml _site/eksempler/
touch _site/.nojekyll
