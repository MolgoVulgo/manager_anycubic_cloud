# pwmb_geom_cpp

Native C++ helpers for PWMB geometry backend (`GEOM_BACKEND=cpp`).

Current scope (Lot C / Phase C):
- `extract_polygons(mask)` using native edge-boundary extraction (C++ port of Python contour semantics).
- Python binding via `pybind11`, exported as module `_pwmb_geom`.

## Build (local)

Prerequisites:
- CMake >= 3.20
- C++17 compiler
- Python 3.11+ headers
- `pybind11` (Python package or CMake package)

Example:

```bash
python -m pip install pybind11
cmake -S pwmb_geom_cpp -B pwmb_geom_cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build pwmb_geom_cpp/build -j
```

Install into current Python env:

```bash
cmake --install pwmb_geom_cpp/build \
  --prefix "$(python -c \"import sysconfig; print(sysconfig.get_paths()['platlib'])\")"
```

Result:
- extension installed as `pwmb_geom/_pwmb_geom*.so`
- module `pwmb_geom` becomes importable by `render3d_core.backend`.
