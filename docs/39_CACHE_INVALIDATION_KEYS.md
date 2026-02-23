### But
Définir exactement ce qui invalide un cache (contours / geometry) pour éviter les incohérences.

### Cache niveaux
1) **Cache Contours** : `PwmbContourStack`
2) **Cache Geometry** : `PwmbContourGeometry`

### Clé cache (contrat)
Doit inclure au minimum :
- `file_signature` : taille + mtime + hash partiel (ou sha256 complet si acceptable)
- `pwmb_version`
- `decoder_kind` : `pw0Img|pwsImg`
- `pws_convention` (si pws : `C0|C1`)
- `lut_signature` (présence + valeurs)

Paramètres build qui invalident :
- `threshold`
- mode binarisation : `index_strict|threshold`
- `xy_stride`, `z_stride`
- filtres morpho : (aire min, open/close, etc.)
- `simplify_epsilon` / paramètres de décimation
- budgets : `max_layers`, `max_vertices`
- mode rendu : `fill|contours|points` (si la géométrie diffère)

### Invariants
- Changer uniquement la **visibilité** (cutoff layer, tri back-to-front) n’invalide pas.
- Toute variation qui modifie les loops ou les triangles invalide.

