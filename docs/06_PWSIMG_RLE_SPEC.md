### Identification
Utiliser ce décodage si : `Machine.LayerImageFormat == "pwsImg"`.

### Unité de lecture
- Octets `u8`.

### Byte RLE
- `bit7` = exposé (1) / non-exposé (0)
- `bits0..6` = répétitions (`reps`)

### Ambiguïté de convention (à traiter explicitement)
Deux conventions existent dans la nature pour ce type d’encodage :
- **C0** : `run_len = reps`
- **C1** : `run_len = reps + 1`

Plutôt que “deviner”, on fixe un contrat d’implémentation **déterministe** :

#### Contrat de sélection de convention
Pour une couche donnée (ou un fichier), on tente un décodage **dry-run** (sans écrire l’image complète) et on choisit la convention qui respecte le mieux les invariants :
1) Le décodage doit produire **exactement** `pixel_count = W*H` pixels **par passe**.
2) Le décodage doit finir **sans overrun** ; un dernier run peut être clampé au pixel restant **uniquement** si la convention sinon valide l’ensemble.
3) On préfère la convention qui :
   - consomme le flux sans résidu important, et/ou
   - colle le mieux à `NonZeroPixelCount` si disponible.

> Une fois choisie, la convention est considérée **stable** pour le fichier (cacheable).

### Anti-aliasing
- Le flux contient `AA` passes.
- Chaque passe produit une image binaire exposé/non.
- On cumule `count_exposed[pixel]` sur `uint16`.

### Projection AA → uint8 (canon)
- `val = round(255 * count / AA)` avec `count ∈ [0..AA]`.
- Garantit : 0→0, AA→255, monotone, stable même si AA ne divise pas 256.

### Erreurs
- Fin prématurée avant `pixel_count` sur une passe ⇒ couche invalide.
- `AA <= 0` ⇒ fichier invalide.

### Vecteurs de test synthétiques (micro)
Ces vecteurs ne valident pas un fichier réel ; ils valident le moteur RLE et le choix de convention.

- **Test A (C1 typique)**
  - `W=4,H=1` (`pixel_count=4`), `AA=1`
  - bytes : `0x80` (exposé, reps=0)
  - C1 → run_len=1 : écrit 1 pixel exposé → OK partiel
  - C0 → run_len=0 : interdit (run nul) → échec

- **Test B (run multiple)**
  - `W=4,H=1`, `AA=1`
  - bytes : `0x83` (exposé reps=3)
  - C0 → 3 pixels ; C1 → 4 pixels (remplit pile)

Ces tests servent à détecter les régressions “run_len=0” et la logique de sélection.

---

