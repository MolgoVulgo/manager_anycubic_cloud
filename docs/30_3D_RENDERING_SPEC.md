### But
Définir la construction d’une représentation 3D à partir des masks, avec préparation GPU.

### Entrées
- `PwmbDocument` (W,H, pitch, layer_height, layers defs)
- `threshold`
- Budgets : `max_layers`, `max_vertices`, `max_xy_stride`
- Qualite preview:
  - `Qualite max (100%)` = toutes les couches + `xy_stride=1`
  - `Qualite intermediaire (66%)` = echantillonnage couches ~66%
  - `Qualite basse (33%)` = echantillonnage couches ~33%

### Sortie
- `PwmbContourStack` : layers → loops monde
- `PwmbContourGeometry` : buffers tri/line/point + ranges par layer

### Conversion pixel → monde
- `pitch_x_mm = PixelSizeUm / 1000`
- `pitch_y_mm = PixelSizeUm / 1000`
- `pitch_z_mm = LayerHeight`
- Convention : centrer modèle (x,y,z) autour de 0 pour navigation.

### Extraction loops
- Depuis `mask` : extraction de contours fermés.
- Nettoyage : suppression micro-îlots (aire min) + simplification.
- Preview: smoothing optionnel des loops (1 passe) avec garde-fous (aire/bbox/orientation).
- Preview: extracteur subpixel optionnel (`contour_extractor=subpixel_halfgrid`) pour reduire l'effet "escalier".

### Holes
- Déterminer `outer` vs `hole` (aire signée + containment).
- Rendu fill : trous retirés via parité (even-odd) ou assignation outer/holes.

### Budgets / LOD
- Stride XY et stride Z (layer skip) ajustables en interactif.
- Décimation agressive au-delà d’un budget vertices.
- Pour limiter les artefacts "carres" en XY:
  - downsampling masque par agregation de blocs (any/max pooling),
  - evite la perte de details fins du sous-echantillonnage brut.

---
