#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
python3 tools/translations/pipeline.py
( cd FarsiMod2 && dotnet build -c Release -v q )
rm -rf dist/FarsiMod2
mkdir -p dist/FarsiMod2
cp -R FarsiMod2/bin/. dist/FarsiMod2/
rm -rf dist/FarsiMod2/bin
( cd dist && rm -f FarsiMod2.zip && zip -qr FarsiMod2.zip FarsiMod2 )
echo "Built dist/FarsiMod2.zip"
