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

