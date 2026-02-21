### But
Éviter les artefacts de transparence/ordre en fixant depth/blend et l’ordre des passes.

### États GPU (contrat)
- **Depth test** :
  - Fill (triangles) : ON
  - Edges (lines) : ON (ou OFF si on veut “toujours visible”, mais alors assumé)
  - Points : ON

- **Blending** :
  - activé si alpha < 1 (fill translucide)
  - fonction standard : src-alpha / one-minus-src-alpha

### Ordre des passes (contrat)
1) Fill triangles (si mode fill)
2) Edges (lines)
3) Points (si mode points ou debug)

### Transparence / back-to-front
- Si fill translucide :
  - trier les **layers visibles** back-to-front,
  - dessiner par ranges layer dans cet ordre.

### Invariants
- Le tri back-to-front ne recompile pas les buffers.
- Changer uniquement l’UI (cutoff/stride) ne rebuilde pas la géométrie.

---

