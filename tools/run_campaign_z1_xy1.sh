#!/usr/bin/env bash
set -euo pipefail

# Full-quality render3d campaign on local PWMB corpus:
# - xy_stride=1
# - z_stride=1
# - python / cpp(native) / cpp(opencv)
# Then generate a consolidated summary report.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CORPUS_DIR="${1:-pwmb_files}"
REPORTS_DIR="${2:-reports}"

cd "${REPO_ROOT}"
export PYTHONPATH=.

mkdir -p "${REPORTS_DIR}"

PYTHON_JSON="${REPORTS_DIR}/render3d_campaign_python_z1_xy1.json"
CPP_NATIVE_JSON="${REPORTS_DIR}/render3d_campaign_cpp_native_z1_xy1.json"
CPP_OPENCV_JSON="${REPORTS_DIR}/render3d_campaign_cpp_opencv_z1_xy1.json"
SUMMARY_PREFIX="${REPORTS_DIR}/render3d_campaign_summary_z1_xy1"

echo "[campaign] corpus=${CORPUS_DIR}"
echo "[campaign] reports=${REPORTS_DIR}"
echo "[campaign] step 1/4 python backend"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend python \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${PYTHON_JSON}"

echo "[campaign] step 2/4 cpp backend (native contours)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl native \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_NATIVE_JSON}"

echo "[campaign] step 3/4 cpp backend (opencv contours)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl opencv \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_OPENCV_JSON}"

echo "[campaign] step 4/4 summary generation"
python tools/render3d_campaign_summary.py \
  --python-report "${PYTHON_JSON}" \
  --cpp-native-report "${CPP_NATIVE_JSON}" \
  --cpp-opencv-report "${CPP_OPENCV_JSON}" \
  --output-prefix "${SUMMARY_PREFIX}"

echo "[campaign] done"
echo "[campaign] summary json: ${SUMMARY_PREFIX}.json"
echo "[campaign] summary md:   ${SUMMARY_PREFIX}.md"
