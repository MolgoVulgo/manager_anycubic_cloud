# 41_lot_a_baseline — Baseline + contrat backend (phase A)

## Objectif
Mettre en place une base de mesure stable sur backend C++:
- un backend geometrique `cpp` unique,
- des invariants geometriques automatiques,
- un outil de baseline sur corpus PWMB.

## Contrat backend
Module: `render3d_core/backend.py`

- Interface: `GeometryBackend`
  - `build_contours(document, threshold, binarization_mode, xy_stride, metrics)`
  - `build_geometry(contour_stack, max_layers, max_vertices, max_xy_stride, metrics)`
- Selection:
  - variable d'environnement `GEOM_BACKEND=cpp` (backend unique).

Ce contrat permet de conserver l'orchestration GUI avec un backend natif unique.

## Invariants geometriques
Module: `render3d_core/invariants.py`

- `contour_area_mm2`
- `mesh_area_mm2`
- `contour_bbox`
- `mesh_bbox`
- `degenerate_triangle_count`
- `build_invariant_snapshot`

Ces checks servent de garde-fou non-regression (aire, bbox, triangles degeneres).

## Baseline corpus
Script: `tools/render3d_baseline.py`

Exemple:

```bash
PYTHONPATH=. python tools/render3d_baseline.py \
  ./corpus_pwmb \
  --recursive \
  --backend cpp \
  --threshold 1 \
  --bin-mode index_strict \
  --output .accloud/baseline/render3d_baseline_cpp.json
```

Options utiles:
- `--xy-stride` pour forcer le stride XY (sinon profil auto)
- `--max-layers`, `--max-vertices` pour tester des budgets preview
- `--max-xy-stride` pour la simplification geometrique

Sortie JSON:
- metriques build (`parse/decode/contours/triangulation/buffers`)
- snapshot d'invariants (`area/bbox/degenerate triangles`)
- signature fichier pour tracer le corpus.

## Validation minimale recommandee
1. Lancer baseline en `cpp` sur le corpus de reference.
2. Conserver le JSON comme reference de non-regression.
3. Rejouer exactement la meme commande apres chaque lot C++.
