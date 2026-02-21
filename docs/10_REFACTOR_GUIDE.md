### Cibles de refactor
1) **Détection de format**
- Source : `Machine.LayerImageFormat` (pas heuristiques sur extension).

2) **pw0Img**
- Passer sur lecture 16-bit big-endian.
- Clamp + ignore trailing.
- LUT `LayerImageColorTable` appliquée au mapping.

3) **pwsImg**
- Verrouiller convention longueur (`reps` vs `reps+1`).
- Projection AA→uint8 monotone.

4) **Binarisation**
- `threshold` explicite.
- Modes recommandés :
  - “géométrie propre” (threshold haut)
  - “conservatif” (threshold bas)

5) **Rendu 3D**
- Buffers GPU canonisés, ranges par layer.
- Pas de rebuild CPU pour des changements purement “visibilité”.

---

