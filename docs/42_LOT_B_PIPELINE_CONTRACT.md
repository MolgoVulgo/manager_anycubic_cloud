# 42_lot_b_pipeline_contract - point d'entree unique build 3D (phase B)

## Objectif
Consolider le pipeline build 3D autour d'une API unique, stable pour la migration C++:
- une seule fonction d'orchestration appelle backend + cache,
- aucun changement fonctionnel du rendu attendu,
- conservation des metriques et des points de logs UI.

## Implementation

### Module pipeline
Nouveau module: `render3d_core/pipeline.py`

- `build_geometry_pipeline(...)`
  - calcule les cles cache contours/geometrie,
  - applique lookup/set cache,
  - appelle le backend (`build_contours`, `build_geometry`) si miss,
  - retourne un `GeometryBuildResult` unifie.
- `stage_cb(stage)` optionnel pour piloter les etapes GUI sans exposer les details internes.

### Viewer
Fichier: `app_gui_qt/dialogs/pwmb3d_dialog.py`

- `_build_geometry_job` passe par `build_geometry_pipeline(...)`.
- Stages GUI preserves:
  - `cache` (lookup/hit contours puis geometry),
  - `decode`,
  - `contours`,
  - `geometry`,
  - puis `upload/done` inchanges.
- Les logs `build.profile` / `build.metrics` conservent `geom_backend`.

### Baseline corpus
Fichier: `tools/render3d_baseline.py`

- Le script appelle aussi `build_geometry_pipeline(...)`.
- Le chemin baseline et viewer partagent donc le meme contrat de build.

## Tests
Nouveau fichier: `tests/unit/test_render3d_pipeline_unit.py`

- `no cache`: backend appele pour contours + geometry.
- `cache hit total`: aucun appel backend.
- `cache partiel`: hit contours, build geometry.
- verification de l'ordre des stages emis.
