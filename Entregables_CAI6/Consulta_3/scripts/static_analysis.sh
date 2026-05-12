#!/usr/bin/env bash
# Static analysis runner for HealthProcurementAuction.sol
set -euo pipefail

CONTRACT="contracts/HealthProcurementAuction.sol"
REPORT_DIR="reports"
mkdir -p "$REPORT_DIR"

echo "[INFO] Slither..."
if command -v slither >/dev/null 2>&1; then
    slither "$CONTRACT" --solc-remaps "@openzeppelin/=node_modules/@openzeppelin/" --json "$REPORT_DIR/slither.json" || true
    slither "$CONTRACT" --solc-remaps "@openzeppelin/=node_modules/@openzeppelin/" > "$REPORT_DIR/slither.txt" 2>&1 || true
    echo "[OK] Slither -> $REPORT_DIR/slither.{json,txt}"
else
    echo "[WARN] Slither no instalado. pip install slither-analyzer"
fi

echo "[INFO] Mythril..."
if command -v myth >/dev/null 2>&1; then
    myth analyze "$CONTRACT" --solv 0.8.24 -o markdown > "$REPORT_DIR/mythril.md" 2>&1 || true
    echo "[OK] Mythril -> $REPORT_DIR/mythril.md"
else
    echo "[WARN] Mythril no instalado. pip install mythril"
fi

echo "[INFO] Solhint..."
if command -v solhint >/dev/null 2>&1; then
    solhint "$CONTRACT" > "$REPORT_DIR/solhint.txt" 2>&1 || true
    echo "[OK] Solhint -> $REPORT_DIR/solhint.txt"
elif command -v npx >/dev/null 2>&1; then
    npx --no-install solhint "$CONTRACT" > "$REPORT_DIR/solhint.txt" 2>&1 || true
    echo "[OK] Solhint local -> $REPORT_DIR/solhint.txt"
else
    echo "[WARN] Solhint no instalado. npm install"
fi

echo "[OK] Reportes en $REPORT_DIR/"
