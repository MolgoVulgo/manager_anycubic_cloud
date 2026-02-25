# 43_lot_c_cpp_contours - C++ v1 contours to polygons

## Scope
Lot C implements phase C from `docs/40_update_to_cpp.md`:
- native module project `pwmb_geom_cpp` (CMake + pybind11),
- `extract_polygons(mask)` in C++ (native edge-boundary extraction, semantic parity with Python contours),
- Python adapter `pwmb_geom` connected to backend contract.

Current status:
- contours extraction path can be native when `_pwmb_geom` is built,
- geometry triangulation remains Python (`build_geometry_v2`) in this lot.
- functional fixes applied after lot C (PW0 adaptive decode, cutoff observability) are tracked in `docs/44_CORRECTIONS_FONCTIONNELLES.md`.
- optional OpenCV contour extractor planning is tracked in `docs/45_LOT_D_OPENCV_OPTION.md`.

## Added files

- `pwmb_geom_cpp/CMakeLists.txt`
- `pwmb_geom_cpp/include/pwmb_geom/extract_polygons.hpp`
- `pwmb_geom_cpp/src/extract_polygons.cpp`
- `pwmb_geom_cpp/src/module.cpp`
- `pwmb_geom_cpp/README.md`
- `pwmb_geom/__init__.py`
- `tools/render3d_compare_backends.py`

## Python integration

`pwmb_geom` now exposes:
- `build_contours(...)`: calls `render3d_core.contours.build_contour_stack(...)` with native pixel extractor.
- `build_geometry(...)`: delegates to `render3d_core.geometry_v2.build_geometry_v2(...)`.

If `_pwmb_geom` is missing, importing `pwmb_geom` raises `ImportError`, so:
- `GEOM_BACKEND=cpp` cleanly falls back to `python` backend.

## Build native module

Prerequisites:
- CMake
- C++17 compiler
- pybind11

Example:

```bash
python -m pip install pybind11
cmake -S pwmb_geom_cpp -B pwmb_geom_cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build pwmb_geom_cpp/build -j
cmake --install pwmb_geom_cpp/build --prefix "$(python -c \"import sysconfig; print(sysconfig.get_paths()['platlib'])\")"
```

## Validation commands

Baseline (python):

```bash
PYTHONPATH=. python tools/render3d_baseline.py <pwmb_or_dir> --recursive --backend python
```

Comparison python vs cpp:

```bash
PYTHONPATH=. python tools/render3d_compare_backends.py <pwmb_or_dir> --recursive --xy-stride 1 --area-tol 1e-3
```

Output report includes:
- area deltas (`contour_area_mm2`, `mesh_area_mm2`),
- bbox deltas (`contour_bbox`, `mesh_bbox`),
- loop deltas (`layers`, `outer_loops`, `hole_loops`).
