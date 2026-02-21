### But
Figer les conventions d’axes et l’ordre mémoire du raster pour éviter les erreurs “miroir/flip” invisibles.

### Conventions raster (contrat)
- Image décodée : `flat uint8` longueur `W*H`.
- Interprétation : **row-major**.
- Index → (x,y) :
  - `x = i % W`
  - `y = i // W`

### Origine 2D (contrat)
- Origine image : **coin haut-gauche** (x croît vers la droite, y croît vers le bas).

### Passage en monde (contrat)
- `pitch_x_mm = PixelSizeUm / 1000`
- `pitch_y_mm = PixelSizeUm / 1000`
- `pitch_z_mm = LayerHeight`

- Monde :
  - `X = (x - cx) * pitch_x_mm`
  - `Y = (cy - y) * pitch_y_mm`  (inversion pour avoir Y vers le haut)
  - `Z = (layer_index - cz) * pitch_z_mm`

### Tests d’orientation (goldens)
- Pour un layer de référence, stocker un `bbox_px` attendu et vérifier :
  - pas de swap X/Y
  - pas de flip vertical
  - pas de mirror horizontal

---

