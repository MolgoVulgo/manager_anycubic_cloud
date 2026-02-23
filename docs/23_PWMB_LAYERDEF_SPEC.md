### But
Décrire où se trouvent les blobs encodés par couche + infos d’expo associées.

### Structure (table framed)
- `TableName[12] == "LAYERDEF"`
- `TableLength` variable.
- Payload :
  - `LayerCount (u32)`
  - `LayerDef[LayerCount]` (taille entrée dépend version)

### Contrat “LayerDef minimal”
Chaque couche expose au minimum :
- `DataAddress (u32)` : offset absolu du blob encodé
- `DataLength (u32)` : taille blob
- `ExposureTime (f32)` (si présent)
- `LayerHeight (f32)` (si présent)
- `NonZeroPixelCount (u32)` (si présent)

### Invariants
- `DataAddress + DataLength` doit être in-bounds.
- Une couche peut être considérée “invalid” si :
  - `DataLength == 0`
  - fin de blob avant d’atteindre `W*H` pixels après décodage

### Politique d’erreur
- Erreur sur une couche : couche skip (ou image noire), mais parsing document continue.

---

