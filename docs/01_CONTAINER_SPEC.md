### Endianness
- Container et structs : **little-endian**.
- Payload `pw0Img` : mots **16-bit big-endian** (spéc ci-dessous).

### FILEMARK
**But** : pointer vers les tables.

Champs conceptuels (ordre exact dépend template/version) :
- `Mark[12]` : ex `ANYCUBIC`.
- `Version (u32)`
- `NumberOfTables (u32)`
- `TableAddresses[NumberOfTables] (u32[])`

### Mapping des tables par version (observé)
- **v516 (8 tables)** :
  1) `HeaderAddress`
  2) `SoftwareAddress`
  3) `PreviewAddress`
  4) `LayerImageColorTableAddress`
  5) `LayerDefinitionAddress`
  6) `ExtraAddress`
  7) `MachineAddress`
  8) `LayerImageAddress`
- **v517 (9 tables)** : même liste + `ModelAddress` (ou autre table additionnelle selon variante).

### Deux patterns de tables
1) **Table “framed”**
   - `TableName[12] + TableLength(u32) + payload(TableLength bytes)`
   - Ex : `HEADER`, `MACHINE`, `LAYERDEF`, `EXTRA`, `PREVIEW`, `PREVIEW2`.
2) **Bloc brut** (selon version)
   - Ex : `LayerImageColorTable` parfois “struct brute” sans `TableName`.

### Règles de robustesse container
- Ne jamais supposer l’ordre croissant des adresses.
- Toute lecture doit être bornée : `offset >= 0`, `offset < file_size`, `offset + size <= file_size`.
- Si `TableName` est attendu : le valider.
- Tables optionnelles : absence ≠ erreur.

---

