# 45_lot_d_opencv_option - extracteur contours C++ OpenCV (optionnel)

## Objectif
Ajouter une implementation OpenCV optionnelle pour l'extraction de contours C++ afin de comparer:
- robustesse topologique,
- performance,
- cout de maintenance/build.

Ce lot est optionnel et ne remplace pas automatiquement l'implementation native actuelle.

## Scope
- Ajouter une seconde implementation C++ contours basee OpenCV:
  - `findContours` sur masque binaire,
  - recuperation de la hierarchie (outer/holes),
  - normalisation orientation/ordre pour rester compatible avec le contrat Python.
- Conserver l'implementation native existante comme reference.
- Exposer un selecteur d'implementation (env/flag) sans casser `GEOM_BACKEND=cpp`.

## Proposition technique

### C++ module
- Ajouter une abstraction interne:
  - `extract_polygons_native(mask)`
  - `extract_polygons_opencv(mask)`
- Selection a l'execution:
  - env suggeree: `GEOM_CPP_CONTOURS_IMPL=native|opencv|auto`
  - valeur par defaut: `native`.

### Build system
- CMake:
  - support `WITH_OPENCV=ON/OFF` (OFF par defaut),
  - l'option `opencv` ne doit etre disponible que si OpenCV est detecte.
- En absence d'OpenCV:
  - build reussi en mode `native` uniquement.

### Integration Python/backend
- `GEOM_BACKEND=cpp` continue de charger `pwmb_geom` comme aujourd'hui.
- Le choix `native/opencv` reste interne au backend C++.

## Validation

### Non-regression fonctionnelle
- Comparaison `python` vs `cpp(native)` vs `cpp(opencv)` sur corpus:
  - `contour_area_mm2`, `mesh_area_mm2`,
  - `contour_bbox`, `mesh_bbox`,
  - `outer_loops`, `hole_loops`, `layers`.
- Tolerances a definir par corpus, avec rapport JSON.

### Performance
- Benchmark sur memes fichiers:
  - temps `decode/contours/triangulation`,
  - throughput global.
- Decision explicite:
  - conserver `native` par defaut,
  - ou basculer par defaut vers `opencv` si gain/robustesse justifies.

## Critere d'acceptation
- Aucune regression fonctionnelle majeure sur le corpus de reference.
- Build C++ stable avec et sans OpenCV.
- Selecteur `native/opencv` documente et teste.

## Etat d'avancement (2026-02-25)
- [x] CMake: option `WITH_OPENCV=ON/OFF` (OFF par defaut), build natif inchange.
- [x] Module C++: selecteur runtime `native|opencv|auto` + sonde disponibilite OpenCV.
- [x] Backend Python `pwmb_geom`: env `GEOM_CPP_CONTOURS_IMPL` avec fallback robuste vers `native`.
- [x] Outils baseline/compare: ajout du flag `--cpp-contours-impl`.
- [x] Campagne corpus complete `python` vs `cpp(native)` vs `cpp(opencv)` (aires/bbox/loops/perf).
- [x] Decision de valeur par defaut (`native` ou `opencv`) basee sur mesures.

## Resultats campagne (protocole z_stride=4)

Corpus:
- `cube.pwmb`
- `raven_skull-12-25-v3.pwmb`
- `raven_skull_19_12.pwmb`

Synthese perf (ms agreges):
- `python`: total `92686.472` (`decode=12860.423`, `contours=39821.191`, `triangulation=40004.858`)
- `cpp(native)`: total `56488.055` (`decode=12824.472`, `contours=5019.381`, `triangulation=38644.202`)
- `cpp(opencv)`: total `63575.497` (`decode=12850.080`, `contours=5189.312`, `triangulation=45536.105`)

Ratios:
- `cpp(native)` vs `python`: `1.641x`
- `cpp(opencv)` vs `python`: `1.458x`
- `cpp(native)` vs `cpp(opencv)`: `1.125x`

Parite fonctionnelle:
- `cpp(native)` vs `python`: parite stricte sur ce corpus (aire contour/mesh, bbox, triangle_count).
- `cpp(opencv)` vs `python`: ecarts observes:
  - `raven_skull-12-25-v3.pwmb`: `triangle_count +1238`
  - `raven_skull_19_12.pwmb`: `triangle_count +4798`, `mesh_area_delta=-39.306489 mm2`

Decision:
- Valeur par defaut recommandee: **`native`**
  - meilleure parite actuelle avec backend Python,
  - meilleure performance globale sur corpus,
  - pas de regression geometrique observee sur les invariants suivis.

Artefacts:
- `reports/render3d_campaign_python_z4.json`
- `reports/render3d_campaign_cpp_native_z4.json`
- `reports/render3d_campaign_cpp_opencv_z4.json`
- `reports/render3d_campaign_summary_z4.json`
- `reports/render3d_campaign_summary_z4.md`

## Execution campagne qualite max (z1/xy1)

Pour la campagne corpus complete en qualite max, utiliser:
- `tools/run_campaign_z1_xy1.sh`

Documentation d'execution:
- `docs/46_LOT_D_CAMPAIGN_RUNBOOK.md`

Sorties attendues:
- `reports/render3d_campaign_python_z1_xy1.json`
- `reports/render3d_campaign_cpp_native_z1_xy1.json`
- `reports/render3d_campaign_cpp_opencv_z1_xy1.json`
- `reports/render3d_campaign_summary_z1_xy1.json`
- `reports/render3d_campaign_summary_z1_xy1.md`
