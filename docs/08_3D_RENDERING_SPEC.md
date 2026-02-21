### But
Définir la construction d’une représentation 3D à partir des masks, avec préparation GPU.

### Entrées
- `PwmbDocument` (W,H, pitch, layer_height, layers defs)
- `threshold`
- Budgets : `max_layers`, `max_vertices`, `max_xy_stride`

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

### Holes
- Déterminer `outer` vs `hole` (aire signée + containment).
- Rendu fill : trous retirés via parité (even-odd) ou assignation outer/holes.

### Budgets / LOD
- Stride XY et stride Z (layer skip) ajustables en interactif.
- Décimation agressive au-delà d’un budget vertices.

---

