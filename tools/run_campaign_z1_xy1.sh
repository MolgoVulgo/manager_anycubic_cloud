#!/usr/bin/env bash
set -euo pipefail

# Full-quality render3d campaign on local PWMB corpus:
# - xy_stride=1
# - z_stride=1
# - cpp(native) / cpp(opencv)
# Then generate a consolidated summary report.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CORPUS_DIR="${1:-pwmb_files}"
REPORTS_DIR="${2:-reports}"
WORKERS_ARG="${3:-}"
PARALLEL_POLICY_ARG="${4:-}"

cd "${REPO_ROOT}"
export PYTHONPATH=.

mkdir -p "${REPORTS_DIR}"

EXTRA_ARGS=()
if [[ -n "${WORKERS_ARG}" ]]; then
  EXTRA_ARGS+=(--workers "${WORKERS_ARG}")
fi
if [[ -n "${PARALLEL_POLICY_ARG}" ]]; then
  EXTRA_ARGS+=(--parallel-policy "${PARALLEL_POLICY_ARG}")
fi

CPP_NATIVE_JSON="${REPORTS_DIR}/render3d_campaign_cpp_native_z1_xy1.json"
CPP_OPENCV_JSON="${REPORTS_DIR}/render3d_campaign_cpp_opencv_z1_xy1.json"
SUMMARY_PREFIX="${REPORTS_DIR}/render3d_campaign_summary_z1_xy1"

echo "[campaign] corpus=${CORPUS_DIR}"
echo "[campaign] reports=${REPORTS_DIR}"
echo "[campaign] workers=${WORKERS_ARG:-auto}"
echo "[campaign] parallel_policy=${PARALLEL_POLICY_ARG:-default}"
echo "[campaign] step 1/3 cpp backend (native contours)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl native \
  --xy-stride 1 \
  --z-stride 1 \
  "${EXTRA_ARGS[@]}" \
  --output "${CPP_NATIVE_JSON}"

echo "[campaign] step 2/3 cpp backend (opencv contours)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl opencv \
  --xy-stride 1 \
  --z-stride 1 \
  "${EXTRA_ARGS[@]}" \
  --output "${CPP_OPENCV_JSON}"

echo "[campaign] step 3/3 summary generation"
python tools/render3d_campaign_summary.py \
  --cpp-native-report "${CPP_NATIVE_JSON}" \
  --cpp-opencv-report "${CPP_OPENCV_JSON}" \
  --output-prefix "${SUMMARY_PREFIX}"

echo "[campaign] done"
echo "[campaign] summary json: ${SUMMARY_PREFIX}.json"
echo "[campaign] summary md:   ${SUMMARY_PREFIX}.md"
