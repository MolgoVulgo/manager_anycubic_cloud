### But
Fixer des vecteurs de test stables (parse + decode + invariants) + des *goldens* pour éviter les régressions silencieuses.

### Fichiers de référence
- `cube.pwmb` (v516, AA=1, pw0Img)
- `cube2.pwmb` (v516, AA=8, pw0Img)
- `misteer.pwmb` (v517, AA=4, pw0Img)

### Assertions minimales (par fichier)
- Signature/version lues correctement.
- Tables clés accessibles (`HEADER`, `MACHINE`, `LAYERDEF`).
- `LayerCount` correct.
- Pour N couches échantillon (ex : 0, 1, mid, last) :
  - decode → taille `W*H`
  - pas de boucle infinie (`run_len != 0`)
  - tolérance trailing `pw0Img` activée

### Goldens recommandés (stables)
Les goldens doivent être calculés sur l’image **décodée** avant binarisation.

Pour chaque fichier, pour `layer_index in {0, 1, 17, 202, last}` (ajuster si hors range) :
1) `nonzero_index_count = count(color_index != 0)` (si on expose `color_index`) **ou** `count(intensity >= 1)` si on ne garde que `uint8`.
2) `bbox_px = (min_x, min_y, max_x, max_y)` sur pixels “matière” (index != 0).
3) `checksum_sample` : hash (ex sha256) sur un échantillon déterministe :
   - concat des 4096 premiers pixels + 4096 pixels au milieu + 4096 derniers pixels.

### Sanity-check optionnel
- Comparer `nonzero_index_count` à `NonZeroPixelCount` (si présent) avec tolérance stricte.

### Objectif
- Capturer : flip/mirror, mauvais mapping LUT, mauvais endianness, mauvais clamp trailing, régression perf (via timings).

---

