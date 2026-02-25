# Reste a Faire

Date: 2026-02-25
Contexte: migration render3d Python -> C++ en cours, avec pipeline unifie et backend C++ contours deja integre.

## Lots realises

- [x] Lot A - Baseline + contrat backend
  - backend selectionnable `python|cpp`,
  - invariants geometriques,
  - script baseline corpus.
- [x] Lot B - Pipeline contract + orchestration viewer
  - point d'entree unique `build_geometry_pipeline(...)`,
  - integration cache/stages/metriques,
  - rendu progressif 2 passes (contours puis fill) dans le viewer.
- [x] Lot C - C++ contours (extracteur natif)
  - module `pwmb_geom_cpp` + bindings `pybind11`,
  - integration backend C++ avec fallback python.
- [x] Correctifs fonctionnels post lots A/B/C
  - decode PW0 adaptatif (`word16` / `byte_token`) pour compatibilite Lychee/Anycubic,
  - observabilite cutoff (`Lcurrent/max` + `cutoff_layer` dans logs draw).

## Lots a faire (priorises)

### Lot D (optionnel) - OpenCV contours backend
- [x] Ajouter implementation OpenCV (`findContours` + hierarchie) en option.
- [x] Ajouter selecteur implementation C++ (`native|opencv|auto`) sans casser `GEOM_BACKEND=cpp`.
- [x] Comparer `python` vs `cpp(native)` vs `cpp(opencv)` (aire/bbox/loops/perf).
- [x] Decider la valeur par defaut (`native` ou `opencv`) selon corpus.
  - Decision: **default = native** (parite fonctionnelle stricte avec Python sur corpus, perf globale meilleure qu'OpenCV).

### Lot E - Triangulation C++
- [x] Integrer triangulation native C++ (ear clipping/axis-aligned path).
- [x] Garantir absence de triangles degeneres (degenerate_triangles=0 sur campagne).
- [x] Verifier parite aire/bbox avec backend Python (campagne post Lot E).

### Lot F - Buffers contigus / zero-copy
- [x] Sorties NumPy contigues float32/uint32 depuis backend C++.
- [x] Limiter les reconstructions Python de vertices/indices.
- [x] Mesurer gain `buffers_ms_total`.

### Lot G - I/O decode couches
- [x] Remplacer re-ouverture fichier par couche par acces persistant (mmap/handle partage).
- [x] Re-mesurer `decode_ms_total` et stabilite multi-workers.

### Lot H - Parallellisation et annulation
- [x] Finaliser strategie threads/process selon sections calculees en C++.
  - Strategie viewer explicite et loggee (`RENDER3D_POOL_KIND/WORKERS`, mode `auto`), avec execution effective en `threads` pour conserver progress/cancellation cooperatives.
- [x] Connecter pleinement l'annulation au build 3D complet.
  - Token branche bout-en-bout (`dialog -> job -> pipeline -> backend -> contours/geometry`) + bouton UI "Cancel build" + restart propre apres annulation.

## Qualite technique et UX (restant)

- [x] Renforcer triangulation polygons+holes non axis-alignes complexes.
  - triangulation scanline generalisee ajoutee (Python + C++) avec fallback ear-clip, tests aire+degeneres sur cas non axis-alignes multi-holes.
- [x] Implementer/valider tri back-to-front camera pour couches translucides.
- [x] Ajouter fallback renderer robuste si OpenGL init/upload echoue.
- [x] Aligner strictement `index_strict` avec `color_index != 0` (pas uniquement intensite best-effort).
- [x] Ajouter messages erreur utilisateur plus explicites (parse/decode/GL) + retry.
- [x] Memorisations des parametres viewer entre ouvertures.

## Tests a ajouter

- [x] Tests unitaires cache/invalidation backend+pipeline.
- [x] Tests unitaires metriques/invariants.
- [x] Tests unitaires decode PW0 variantes + fallback integration.
- [x] Tests integration viewer (build async -> upload -> draw/ranges visibles).
- [x] Goldens PWMB de non-regression (orientation/bbox/checksum).
- [x] E2E GUI minimal depuis Files -> Viewer -> rebuild -> cutoff/stride.

## Qualite contours percue (nouveau)

### Lot K - Contours moins "carres" en preview
- [x] K1: qualite 100% -> `xy_stride=1` force.
- [x] K1: downsampling XY par blocs (`any/max pooling`) au lieu de decimation brute.
- [x] K2: smoothing preview des loops (1 passe) avec garde-fous aire/bbox + orientation.
- [x] K3: extraction subpixel half-grid en option backend/pipeline (`contour_extractor`), active dans le viewer.
- [x] K4: comparaison OpenCV orientee lissage (`TC89_*`) vs natif.
  - Campagne z4/xy4 executee (`simple` vs `tc89_l1` vs `tc89_kcos`) avec synthese dediee.
  - Decision: `simple` reste la meilleure option OpenCV; default global conserve sur `cpp(native)`.
- [x] K5: finitions GPU (AA/palette/epaisseur contours) orientees lisibilite.
  - MSAA active (best-effort) + logs `requested/effective`.
  - Style draw ajuste: line width, point size, fill alpha scale (configurables via env).

Reference:
- `docs/53_LOT_K_CONTOURS_QUALITY.md`
