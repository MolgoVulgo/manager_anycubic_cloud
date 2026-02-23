### But
- Lire un fichier **.pwmb** et produire une représentation 3D interactive.
- Séparer strictement : **container** → **metadata** → **décodage layer** → **binarisation** → **contours** → **géométrie** → **rendu**.

### Pipeline canonique (contrats)
1. **Parse container**
   - Lire `FILEMARK` (signature, version, nombre de tables, adresses).
   - Valider intégrité minimale (bornes fichier, cohérence des offsets).
2. **Lire tables clés**
   - `HEADER` : résolution, pitch, layer height, AA, paramètres impression.
   - `MACHINE` : `LayerImageFormat` (ex: `pw0Img`, `pwsImg`), nom machine.
   - `LAYERDEF` : `LayerCount` + `DataAddress/DataLength` par couche + champs utiles.
   - `LayerImageColorTable` : LUT (si présente) pour mapping niveaux.
   - Tables optionnelles : `PREVIEW`, `PREVIEW2`, `SOFTWARE`, `MODEL`, `SUBLAYERDEF`, `EXTRA`.
3. **Décodage d’une couche**
   - Entrée : `(DataAddress, DataLength)` + `W,H` + `format` (+ LUT si applicable).
   - Sortie : image **flat** `uint8` de taille `W*H`.
4. **Binarisation**
   - `mask = (img >= threshold)`.
   - `threshold` est un paramètre **explicite** (pas de seuil implicite “>0”).
5. **Contours / Loops**
   - Extraction de boucles fermées (outer + holes) sur le masque.
   - Simplification (decimate) et budgets.
6. **Géométrie 3D**
   - Conversion pixel → mm + empilement Z.
   - Construction buffers triangles/lignes/points.
7. **Rendu**
   - **GPU-first** (OpenGL) : draw triangles/lignes/points.
   - CPU fallback : rendu 2D/3D simplifié + oracle (even-odd) selon besoin.

### Sorties attendues
- `PwmbDocument` : metadata + table des couches.
- `PwmbContourStack` : loops par couche, déjà en unités monde.
- `PwmbContourGeometry` : buffers prêts à upload GPU + ranges par layer.

---

