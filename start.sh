#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
DEPS_STAMP="${VENV_DIR}/.deps_installed"
REQUIRED_IMPORTS="import PySide6, httpx, numpy, cv2"
INSTALL_TARGET="${ROOT_DIR}[metrics]"
SYSTEM_PYTHON="$(command -v python3 || true)"

cd "${ROOT_DIR}"

if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

VENV_CAN_RUN=0
SYSTEM_CAN_RUN=0

if python -c "${REQUIRED_IMPORTS}" >/dev/null 2>&1; then
  VENV_CAN_RUN=1
fi

if [ -n "${SYSTEM_PYTHON}" ] && [ "${SYSTEM_PYTHON}" != "$(command -v python)" ] && "${SYSTEM_PYTHON}" -c "${REQUIRED_IMPORTS}" >/dev/null 2>&1; then
  SYSTEM_CAN_RUN=1
fi

if [ "${VENV_CAN_RUN}" -eq 0 ] && [ "${SYSTEM_CAN_RUN}" -eq 1 ]; then
  exec "${SYSTEM_PYTHON}" -m app_gui_qt.app "$@"
fi

if [ ! -f "${DEPS_STAMP}" ] || [ "${ROOT_DIR}/pyproject.toml" -nt "${DEPS_STAMP}" ] || [ "${VENV_CAN_RUN}" -eq 0 ]; then
  if pip install -e "${INSTALL_TARGET}"; then
    touch "${DEPS_STAMP}"
  else
    echo "Warning: installation in .venv failed, trying system Python." >&2
  fi
fi

if python -c "${REQUIRED_IMPORTS}" >/dev/null 2>&1; then
  exec python -m app_gui_qt.app "$@"
fi

if [ "${SYSTEM_CAN_RUN}" -eq 1 ]; then
  exec "${SYSTEM_PYTHON}" -m app_gui_qt.app "$@"
fi

echo "Error: missing dependencies (PySide6, httpx, numpy, cv2)." >&2
exit 1
