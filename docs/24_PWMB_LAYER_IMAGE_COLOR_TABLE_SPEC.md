### But
Mapper les niveaux “index” (souvent 4-bit `0..15`) vers une intensité `uint8` (`0..255`) **sans casser** :
- la sémantique “vide vs matière”,
- la binarisation,
- l’interprétation de `NonZeroPixelCount`.

### Règle canonique (vide)
- **Index 0 = vide**.
- Donc : **`color_index == 0` ⇒ `intensity = 0`**.

> Important : même si une LUT place une valeur non-nulle à l’index 0 (ex `0x0f`), l’index 0 reste **sémantiquement vide**. La LUT sert à l’AA/grayscale, pas à redéfinir l’état “matière”.

### Cas A — LUT présente (v516 typique)
Champs observés côté outil :
- `UseFullGreyscale (u32)`
- `GreyMaxCount (u32)` (souvent `16`)
- `Grey[GreyMaxCount] (u8[])`
- `Unknown (u32)`

Mapping intensité :
- si `color_index == 0` → `0`
- sinon `intensity = LUT[color_index]`

### Cas B — LUT absente / minimale
- Fallback linéaire :
  - si `color_index == 0` → `0`
  - sinon `intensity = color_index * 17` (1→17 … 15→255)

### Contrats “NonZeroPixelCount”
- `NonZeroPixelCount` (si présent en `LAYERDEF`) doit être comparé à **`count(color_index != 0)`**.
- Ne pas comparer à `count(intensity != 0)` (car LUT peut rendre non-zéro des indices non-matière si mal appliquée).

### Contrats de binarisation (recommandés)
Deux modes distincts :
1) **Mode “matière stricte”** : `mask = (color_index != 0)` (ne dépend pas du mapping intensité).
2) **Mode “seuil”** : `mask = (intensity >= threshold)` (utile si grayscale réel).

Le code doit supporter les deux ; le choix est un paramètre explicite.

---

