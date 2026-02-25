# 51_LOT_I_TRIANGULATION_ROBUSTNESS

Date: 2026-02-25

## Objectif
Renforcer la triangulation des polygons+holes non axis-alignes complexes pour eviter:
- pertes de surface,
- triangles degeneres,
- echec de merge holes en ear-clip sur certains profils geometriques.

## Changements implementes

### 1) Nouveau chemin robuste scanline (Python)
Fichier: `render3d_core/geometry_v2.py`

- Ajout d'une triangulation scanline generalisee:
  - `_triangulate_scanline_loops(loops)`
  - `_x_at_y(p1, p2, y)`
- Integration dans `_triangulate_polygon_with_holes(...)`:
  - non-axis: tentative scanline d'abord,
  - fallback ear-clip merge holes,
  - dernier fallback scanline si ear-clip vide.

Resultat: les cas non-axis multi-holes ne dependent plus uniquement du bridge+ear-clip.

### 2) Parite native C++
Fichier: `pwmb_geom_cpp/src/triangulate.cpp`

- Ajout du meme principe scanline cote C++:
  - `x_at_y(...)`
  - `triangulate_scanline_loops(...)`
- Integration dans `triangulate_polygon_with_holes(...)`:
  - axis -> chemin axis existant,
  - non-axis -> scanline prioritaire,
  - fallback ear-clip,
  - fallback final scanline.

Resultat: comportement aligne entre backends Python et C++.

## Tests ajoutes/etendus

### Python geometry
Fichier: `tests/unit/test_render3d_build_unit.py`

- `test_build_geometry_v2_non_axis_aligned_holes_preserve_area`
  - cas non-axis avec 2 holes,
  - verification aire mesh ~= aire contour.

### Native C++ triangulation
Fichier: `tests/unit/test_pwmb_geom_triangulation_unit.py`

- `test_native_triangulation_non_axis_aligned_holes_preserves_area`
  - meme type de cas non-axis multi-holes,
  - verification aire triangulee ~= aire polygonale.

## Validation

Commandes executees:
- `cmake -S pwmb_geom_cpp -B pwmb_geom_cpp/build -DCMAKE_BUILD_TYPE=Release`
- `cmake --build pwmb_geom_cpp/build -j`
- `cmake --install pwmb_geom_cpp/build --prefix .`
- `PYTHONPATH=. pytest -q tests/unit`

Resultat:
- `74 passed`

## Impact

- Robustesse triangulation amelioree sur geometries non axis-alignes avec trous complexes.
- Parite Python/C++ maintenue avec couverture de tests dedies.
