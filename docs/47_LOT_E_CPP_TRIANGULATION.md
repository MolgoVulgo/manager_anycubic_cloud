# 47_lot_e_cpp_triangulation - triangulation native C++

## Objectif
Ajouter la triangulation native C++ dans le backend `GEOM_BACKEND=cpp` pour reduire le cout CPU de la phase `triangulation` tout en conservant la parite geometrique entre variantes C++.

## Implementation

### Module C++
- Nouveau header:
  - `pwmb_geom_cpp/include/pwmb_geom/triangulate.hpp`
- Nouvelle implementation:
  - `pwmb_geom_cpp/src/triangulate.cpp`
- Binding pybind:
  - `triangulate_polygon_with_holes(outer, holes)` expose dans `_pwmb_geom`.

Algorithmes integres:
- chemin axis-aligned (scanline deterministic),
- fallback general (merge holes + ear clipping),
- filtrage des triangles degeneres (`abs(cross) > 1e-12`).

### Integration Python backend C++
- `pwmb_geom.build_geometry(...)` utilise desormais la triangulation native C++ par defaut.
- Selecteur runtime:
  - `GEOM_CPP_TRIANGULATION_IMPL=native|auto`
  - defaut: `native` (mode `python` supprime).
- Integration sans rupture via `render3d_core.geometry_v2(..., triangulator=...)`.

## Validation

### Tests unitaires
- `tests/unit/test_pwmb_geom_triangulation_unit.py`
  - aire triangulee = aire polygonale (outer - holes),
  - absence de triangles degeneres,
  - coherence `native` vs `auto` sur `build_geometry`.

### Campagne corpus (post Lot E, protocole z4)
Rapports:
- `reports/render3d_campaign_python_z4_lotE.json`
- `reports/render3d_campaign_cpp_native_z4_lotE.json`
- `reports/render3d_campaign_cpp_opencv_z4_lotE.json`
- `reports/render3d_campaign_summary_z4_lotE.json`
- `reports/render3d_campaign_summary_z4_lotE.md`

Resultats clefs:
- Parite fonctionnelle `cpp(native)` vs `cpp(opencv)` conservee sur le corpus (aire/bbox/triangle_count).
- Degenerate triangles: `0` sur tous les cas mesures.
- `cpp(native)` reste plus rapide en total que `cpp(opencv)` (~`1.09x`), malgre un `contours_ms` parfois inferieur en OpenCV.

## Decision
- Statut Lot E: **integre et valide** dans le backend C++.
- Valeur operationnelle recommandee:
  - `GEOM_BACKEND=cpp`
  - `GEOM_CPP_TRIANGULATION_IMPL=native`
