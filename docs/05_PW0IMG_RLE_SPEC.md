### Identification
Utiliser ce décodage si : `Machine.LayerImageFormat == "pw0Img"`.

### Unité de lecture
- Lire des **mots 16-bit big-endian**.

### Format d’un mot
- `color_index = (word >> 12) & 0xF`
- `run_len = word & 0x0FFF`

### Décodage
- Répéter : écrire `run_len` pixels de valeur `color_index` (converti via LUT ou fallback) jusqu’à remplir `pixel_count = W*H`.

### Robustesse (obligatoire)
- `run_len == 0` ⇒ couche invalide.
- **Clamp** du dernier run si dépasse `pixel_count`.
- **Trailing** : ignorer les mots restants dans le blob si `pixel_count` atteint avant fin blob.

### Sortie
- Image `uint8` flat de taille `W*H`.

---

