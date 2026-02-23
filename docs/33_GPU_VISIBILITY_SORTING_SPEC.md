### Entrées UI
- `layer_max_index` (cutoff)
- `force_full_quality` (désactive stride)
- `contour_only` (pas de fill)

### Stride interactif
- Si pas full quality : `stride_z` dynamique pour limiter #layers visibles.

### Tri back-to-front
- Produire la liste des layers visibles triée back-to-front (dépend camera/MVP).
- Draw dans cet ordre en consommant les ranges.

### Invariants
- Changer cutoff/stride ne modifie pas les buffers, uniquement la liste/ranges rendus.

---

