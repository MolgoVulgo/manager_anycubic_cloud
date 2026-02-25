# 48_lot_f_zero_copy_buffers - buffers contigus float32/uint32

## Objectif
Reduire le cout de preparation des buffers GPU en supprimant les reconstructions Python repetitives et en sortant un format contigu exploitable directement:
- vertices `float32` contigus (shape `N x 4`)
- indices `uint32` contigus (`triangles: M x 3`, `lines: K x 2`, `points: P`)

## Implementation

### 1) Materialisation contigue dans `build_geometry_v2`
- Fichier: `render3d_core/geometry_v2.py`
- Ajout d'une finalisation unique de fin de build:
  - conversion des buffers geometry en `np.ndarray` contigus `float32`
  - construction des indices sequentiels `uint32`
  - alimentation de `metrics.buffers_ms_total`

### 2) Contrat `PwmbContourGeometry` etendu
- Fichier: `render3d_core/types.py`
- Ajouts:
  - `triangle_indices`
  - `line_indices`
  - `point_indices`

### 3) Viewer: suppression des reconversions inutiles
- Fichier: `app_gui_qt/dialogs/pwmb3d_dialog.py`
- Upload VBO:
  - reutilise directement les buffers `np.ndarray` contigus quand disponibles
  - fallback robuste pour anciens formats
- Fit camera:
  - calcul bbox via buffers numpy, sans reconstruire un `cloud` Python complet

### 4) Invariants et outils
- Fichier: `render3d_core/invariants.py`
  - calculs area/bbox vectorises sur buffers numpy
- Fichier: `tools/render3d_campaign_summary.py`
  - prise en compte de `buffers_ms_total` dans l'agregat et le total

### 5) Binding C++ additionnel (prepare la suite)
- Fichier: `pwmb_geom_cpp/src/module.cpp`
- Nouvelle API exposee:
  - `triangulate_polygon_with_holes_indexed(...) -> {vertices, indices}`
- Etat:
  - disponible et testee
  - non activee par defaut dans le pipeline courant (le chemin liste reste le plus robuste ici)

## Validation

### Tests
- `PYTHONPATH=. pytest tests/unit -q`
- Resultat: `66 passed`

### Campagne corpus post Lot F (protocole z4/xy4)
Rapports:
- `reports/render3d_campaign_cpp_native_z4_lotF.json`
- `reports/render3d_campaign_cpp_opencv_z4_lotF.json`
- `reports/render3d_campaign_summary_z4_lotF.json`
- `reports/render3d_campaign_summary_z4_lotF.md`

Notes:
- La reference Python reutilisee pour la synthese est `reports/render3d_campaign_python_z4_lotE.json` (meme protocole `z4/xy4`).
- Lot F cible principalement la reduction du cout buffers sur le chemin C++.

## Resultats cles (summary z4_lotF)
- `cpp_native` total: `48745.541 ms`
- `cpp_opencv` total: `54364.442 ms`
- `cpp_native` vs `python`: `2.625x`
- `cpp_opencv` vs `python`: `2.354x`
- `cpp_native` vs `cpp_opencv`: `1.115x`
- `buffers_ms_total`:
  - native: `4341.874 ms`
  - opencv: `3944.575 ms`

## Decision
- Statut Lot F: **integre**
- Defaut operationnel conserve:
  - `GEOM_BACKEND=cpp`
  - `GEOM_CPP_CONTOURS_IMPL=native`
  - `GEOM_CPP_TRIANGULATION_IMPL=native`
