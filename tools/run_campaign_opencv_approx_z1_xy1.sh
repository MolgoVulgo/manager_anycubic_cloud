#!/usr/bin/env bash
set -euo pipefail

# OpenCV approximation campaign on full quality:
# - xy_stride=1
# - z_stride=1
# - python / cpp(native) / cpp(opencv:simple|tc89_l1|tc89_kcos)
# Then generate a consolidated summary focused on OpenCV approx variants.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CORPUS_DIR="${1:-pwmb_files}"
REPORTS_DIR="${2:-reports}"

cd "${REPO_ROOT}"
export PYTHONPATH=.

mkdir -p "${REPORTS_DIR}"

PYTHON_JSON="${REPORTS_DIR}/render3d_campaign_python_z1_xy1_lotK4.json"
CPP_NATIVE_JSON="${REPORTS_DIR}/render3d_campaign_cpp_native_z1_xy1_lotK4.json"
CPP_OPENCV_SIMPLE_JSON="${REPORTS_DIR}/render3d_campaign_cpp_opencv_simple_z1_xy1_lotK4.json"
CPP_OPENCV_TC89_L1_JSON="${REPORTS_DIR}/render3d_campaign_cpp_opencv_tc89_l1_z1_xy1_lotK4.json"
CPP_OPENCV_TC89_KCOS_JSON="${REPORTS_DIR}/render3d_campaign_cpp_opencv_tc89_kcos_z1_xy1_lotK4.json"
SUMMARY_PREFIX="${REPORTS_DIR}/render3d_campaign_opencv_approx_summary_z1_xy1_lotK4"

echo "[campaign-lotK4] corpus=${CORPUS_DIR}"
echo "[campaign-lotK4] reports=${REPORTS_DIR}"

echo "[campaign-lotK4] step 1/6 python backend"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend python \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${PYTHON_JSON}"

echo "[campaign-lotK4] step 2/6 cpp backend (native contours)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl native \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_NATIVE_JSON}"

echo "[campaign-lotK4] step 3/6 cpp backend (opencv simple)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl opencv \
  --cpp-opencv-approx simple \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_OPENCV_SIMPLE_JSON}"

echo "[campaign-lotK4] step 4/6 cpp backend (opencv tc89_l1)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl opencv \
  --cpp-opencv-approx tc89_l1 \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_OPENCV_TC89_L1_JSON}"

echo "[campaign-lotK4] step 5/6 cpp backend (opencv tc89_kcos)"
python tools/render3d_baseline.py \
  "${CORPUS_DIR}" \
  --recursive \
  --backend cpp \
  --cpp-contours-impl opencv \
  --cpp-opencv-approx tc89_kcos \
  --xy-stride 1 \
  --z-stride 1 \
  --output "${CPP_OPENCV_TC89_KCOS_JSON}"

echo "[campaign-lotK4] step 6/6 summary generation"
python tools/render3d_opencv_approx_summary.py \
  --python-report "${PYTHON_JSON}" \
  --cpp-native-report "${CPP_NATIVE_JSON}" \
  --cpp-opencv-report "${CPP_OPENCV_SIMPLE_JSON}" --opencv-label simple \
  --cpp-opencv-report "${CPP_OPENCV_TC89_L1_JSON}" --opencv-label tc89_l1 \
  --cpp-opencv-report "${CPP_OPENCV_TC89_KCOS_JSON}" --opencv-label tc89_kcos \
  --output-prefix "${SUMMARY_PREFIX}"

echo "[campaign-lotK4] done"
echo "[campaign-lotK4] summary json: ${SUMMARY_PREFIX}.json"
echo "[campaign-lotK4] summary md:   ${SUMMARY_PREFIX}.md"
