# 49_lot_g_io_decode - I/O decode couches (reader persistant)

## Objectif
Supprimer l'overhead de re-ouverture fichier par couche pendant le decode PWMB et verifier la stabilite en execution multi-workers.

## Implementation

### 1) Reader persistant `mmap|handle`
- Fichier: `pwmb_core/container.py`
- Ajouts:
  - `LayerBlobReader` (acces aleatoire persistant, mode `mmap` avec fallback `handle`)
  - `open_layer_blob_reader(...)`
  - `decode_layer(..., reader=...)` pour reutiliser un reader deja ouvert

### 2) Pipeline contours: reuse du reader
- Fichier: `render3d_core/contours.py`
- `build_contour_stack(...)`:
  - ouvre un reader unique au debut du stage decode
  - passe `reader` a chaque appel `decode_layer(...)`
  - fallback automatique vers mode legacy `per_layer_open` si le reader n'est pas disponible
  - expose `decode_io_mode` dans les logs stage/contours

### 3) Autres chemins impactes
- Fichier: `pwmb_core/export.py`
  - export PNG multi-couches reutilise un reader unique
- Fichier: `app_gui_qt/dialogs/pwmb3d_dialog.py`
  - `_ensure_pws_convention(...)` lit les blobs via reader persistant

## Validation

### Tests
- `PYTHONPATH=. pytest tests -q`
- Resultat: `95 passed`

### Stabilite multi-workers decode
- Rapport:
  - `reports/render3d_decode_stability_lotG.json`
- Resultat:
  - `workers=8`, `passes=3`, `layers_sampled=96`
  - `reader_mode=mmap`
  - `failures=[]`
  - `stable=true` (meme checksum non-zero sur les 3 passes)

### Re-mesure decode (protocole z4/xy4, corpus)
Rapports:
- `reports/render3d_campaign_cpp_native_z4_lotG.json`
- `reports/render3d_campaign_cpp_opencv_z4_lotG.json`
- `reports/render3d_campaign_summary_z4_lotG.json`
- `reports/render3d_campaign_summary_z4_lotG.md`

Comparaison Lot F -> Lot G (`decode_ms_total` agrege):
- `cpp(native)`: `12669.262 -> 12588.717` (`-80.545 ms`)
- `cpp(opencv)`: `12561.101 -> 12537.858` (`-23.243 ms`)

Observation:
- gain decode mesurable mais modere sur ce corpus (le cout dominant reste contours/triangulation).
- le principal resultat Lot G est la suppression des open/seek repetes et la stabilite du chemin I/O sous charge threads.

## Decision
- Statut Lot G: **integre**
- Prochaine priorite recommandee: Lot H (strategie parallellisation + annulation bout-en-bout).
