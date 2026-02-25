# pwmb_geom_cpp

Native C++ helpers for PWMB geometry backend (`GEOM_BACKEND=cpp`).

Current scope (Lot C / Phase C):
- `extract_polygons(mask)` using native edge-boundary extraction (C++ port of Python contour semantics).
- `triangulate_polygon_with_holes(outer, holes)` for native fill triangulation.
- `triangulate_polygon_with_holes_indexed(outer, holes)` returning contiguous buffers:
  - `vertices` (`float32`, `N x 2`)
  - `indices` (`uint32`, `M x 3`)
- Python binding via `pybind11`, exported as module `_pwmb_geom`.
- Optional (Lot D): OpenCV contours implementation (`findContours`) selectable at runtime.

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

Build with optional OpenCV backend:

```bash
cmake -S pwmb_geom_cpp -B pwmb_geom_cpp/build-opencv -DCMAKE_BUILD_TYPE=Release -DWITH_OPENCV=ON
cmake --build pwmb_geom_cpp/build-opencv -j
```

Install into current Python env:

```bash
cmake --install pwmb_geom_cpp/build \
  --prefix "$(python -c \"import sysconfig; print(sysconfig.get_paths()['platlib'])\")"
```

Result:
- extension installed as `pwmb_geom/_pwmb_geom*.so`
- module `pwmb_geom` becomes importable by `render3d_core.backend`.

## Runtime selector

When `GEOM_BACKEND=cpp` is active:

- `GEOM_CPP_CONTOURS_IMPL=native` (default): native C++ extractor.
- `GEOM_CPP_CONTOURS_IMPL=opencv`: OpenCV extractor (requires build with `WITH_OPENCV=ON`).
- `GEOM_CPP_CONTOURS_IMPL=auto`: uses OpenCV when available, otherwise native.
- `GEOM_CPP_TRIANGULATION_IMPL=native` (default): native C++ triangulation.
- `GEOM_CPP_TRIANGULATION_IMPL=python`: fallback to Python triangulation path.
- `GEOM_CPP_TRIANGULATION_IMPL=auto`: native when available, otherwise python.
