### Conventions
- `u32` : little-endian
- `f32` : IEEE754 little-endian
- `string` : ASCII/UTF-8, souvent fixed-size ou null-terminated selon table

### HEADER (table framed)
**Champs minimum à extraire** (contrat de fonctionnalité) :
- `PixelSizeUm (f32)`
- `LayerHeight (f32)`
- `ExposureTime (f32)`
- `BottomExposureTime (f32)`
- `BottomLayersCount (u32)`
- `AntiAliasing (u32)`
- `ResolutionX (u32)`
- `ResolutionY (u32)`
- (optionnels) `WaitTimeBeforeCure`, `LiftHeight`, `LiftSpeed`, `RetractSpeed`, etc.

**Note** : la présence exacte et l’ordre doivent être drivés par le template/longueur.

### MACHINE (table framed)
**Champs minimum** :
- `MachineName (string)`
- `LayerImageFormat (string)` : ex `pw0Img`, `pwsImg`
- `MaxAntialiasingLevel (u32)`
- `DisplayWidth/DisplayHeight/MachineZ (f32)` (si présents)

### PREVIEW / PREVIEW2 (table framed)
- `ResolutionX`, `ResolutionY` + `DataSize` + buffer.
- Buffer typiquement `W*H*2` (RGB565) — à traiter en best-effort.

### SOFTWARE / MODEL / SUBLAYERDEF
- Parsing best-effort.
- Ne jamais casser le parsing principal si ces tables sont atypiques.

### EXTRA (table framed)
- Longueur variable selon version.
- Contrat : lire selon `TableLength` et exposer une structure “lift profile” normalisée.

---


### Offsets observés (OBSERVED(CODE-LEGACY))
Ces offsets ont été utilisés avec succès dans l’app legacy. Ils servent de **référence** pour un parser “v1”, mais le design canonique reste basé sur les tables (`FILEMARK` → tables → `HEADER` etc.) quand disponibles.

- `pixel_size_um` : `HEADER.base + 0` (float32 LE)
- `layer_height` : `HEADER.base + 4` (float32 LE)
- `anti_aliasing` : `HEADER.base + 40` (int32 LE)
- `resolution_x` : `HEADER.base + 44` (int32 LE)
- `resolution_y` : `HEADER.base + 48` (int32 LE)

LayerDef minimal (entrée 32 bytes, OBSERVED(CODE-LEGACY)) :
- `data_address` @+0 (uint32 LE)
- `data_length` @+4 (uint32 LE)
- `layer_height` @+20 (float32 LE)
- `non_zero` @+24 (uint32 LE)

