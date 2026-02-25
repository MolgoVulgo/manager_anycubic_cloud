# 50_LOT_H_PARALLEL_CANCEL

Date: 2026-02-25

## Objectif
- Finaliser la strategie d'execution `threads/processes` pour le viewer 3D.
- Connecter l'annulation de build en bout-en-bout (UI -> pipeline -> backends).

## Decisions de strategie
- Nouvelles variables d'environnement:
  - `RENDER3D_POOL_KIND=auto|threads|processes`
  - `RENDER3D_POOL_WORKERS=<int>`
- Mode `auto`:
  - backend `cpp` -> `threads` (sections chaudes natives, GIL relache)
  - backend `python` -> `threads` (priorite a l'annulation cooperative et au progress UI)
- Si `RENDER3D_POOL_KIND=processes` est demande:
  - fallback explicite vers `threads` pour le viewer (raison loggee), afin de garder cancellation/progress coherents.

## Annulation bout-en-bout
- UI:
  - ajout bouton `Cancel build`.
  - si `Rebuild` pendant un build actif: annule le build courant puis relance automatiquement.
- Job async:
  - `_build_geometry_job(...)` accepte `cancel_token`, `pool_kind`, `workers`.
  - checkpoints d'annulation avant/apres parse, convention PWS, pipeline.
- Pipeline:
  - `build_geometry_pipeline(..., cancel_token=...)` avec checkpoints cache/contours/geometry.
- Backends:
  - contrat backend enrichi avec `cancel_token`.
  - backend C++: compat ascendante (retry sans `cancel_token` si module natif ancien).
- Stages CPU:
  - `build_contour_stack(..., cancel_token=...)` checkpoints decode/contours.
  - `build_geometry_v2(..., cancel_token=...)` checkpoints triangulation/lignes/points.

## Logs
- Nouveaux evenements principaux:
  - `build.runner_strategy`
  - `ui.cancel` / `ui.cancelled`
  - `build.cancelled`
  - `build.stage_cancel` (contours, geometry)

## Tests ajoutes
- `tests/unit/test_render3d_build_unit.py`
  - annulation sur `build_contour_stack`
  - annulation sur `build_geometry_v2`
- `tests/unit/test_render3d_pipeline_unit.py`
  - annulation avant tout appel backend
  - annulation entre contours et geometry
- `tests/unit/test_render3d_backend_unit.py`
  - compat backend C++ sans argument `cancel_token`

## Validation
- Commande executee:
  - `PYTHONPATH=. pytest -q tests/unit`
- Resultat:
  - `72 passed`
