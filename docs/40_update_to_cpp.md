# 40_update_to_cpp — Plan de bascule Python → C++ (générateur de géométrie PWMB)

## 0) Cible et contrainte
- **Cible** : accélérer la **création du mesh** à partir des couches PWMB (extraction contours + triangulation + buffers).
- **Hors-scope** : moteur de rendu (OpenGL/scene/shaders/caméra) — inchangé.
- **Contrainte** : pas de changement fonctionnel visible (mesh équivalent : topologie/aires/bbox).

## 1) Diagnostic (où le temps part)
- Hot paths actuels en Python pur :
  - Extraction de boucles `_extract_loops()` : parcours **par pixel** + dict/set → coût ~ **surface** (O(W×H)) au lieu du périmètre.
  - Triangulation / trous : ear clipping / scanline Python + allocations (tuples/lists) → CPU + GC.
  - Threads inefficaces à cause du **GIL** tant que le calcul est Python.
- I/O : `decode_layer()` rouvre le fichier par couche → overhead inutile, pénalise le multiproc.

## 2) Objectifs mesurables
- Sur un set PWMB représentatif :
  - **x10 à x100** sur les couches “pleines” (gain principal via extraction contours native).
  - **x3 à x20** sur triangulation (gain via algo natif / compilé).
  - Scaling multi-cœurs : 1→N workers avec courbe quasi-linéaire si I/O propre.
- Métriques à suivre (par couche) : `decode_ms`, `contours_ms`, `tri_ms`, `buffers_ms`, `total_ms`, + nb loops/points/triangles.

## 3) Contrat d’interface (gel fonctionnel)
Définir un contrat unique entre “extraction” et “mesh builder”, pour pouvoir remplacer l’impl sans toucher au reste.

### 3.1 Entrées
- Une couche sous forme :
  - **mask binaire** (uint8) dimension W×H **ou** (option avancée) runs RLE.
  - paramètres de calibration : `pixel_size`, `origin`, `z_height`/index couche.

### 3.2 Sorties
- Polygones 2D :
  - `outers[]` : liste de contours extérieurs
  - `holes[]` : liste de trous par outer (mapping hiérarchique)
  - orientation et ordre **définis** (CW/CCW)
- Mesh :
  - `vertices` : float32 contigu (x,y,z)
  - `indices` : uint32 contigu (triangles)
  - (option) `normals` si nécessaire

### 3.3 Invariants
- Aire 2D par couche (outer – holes) ≈ identique (tolérance fixée)
- bbox identique (tolérance fixée)
- pas de triangles dégénérés

## 4) Choix d’intégration C++ (recommandé)

### 4.1 Option retenue : **lib C++ + bindings Python (pybind11)**
- Avantages :
  - garde l’orchestration Python existante
  - remplace seulement les hot paths
  - échange de buffers **zéro-copie** via NumPy
  - permet multi-thread Python si le calcul est en C++ (GIL relâché)
- Livrable : `pwmb_geom` (module Python) chargé comme une dépendance interne.

### 4.2 Options alternatives (non retenues par défaut)
- **CLI C++** (stdin/out ou fichiers) : facile à isoler, mais overhead sérialisation + gestion fichiers.
- **ctypes/cffi** : possible, mais moins ergonomique / typage fragile.

## 5) Stack algo (C++ natif)

### 5.1 Extraction contours
- Implémenté (Lot C) : **extracteur natif C++** (edge-boundary extraction),
  - port sémantique de la logique Python (`_extract_loops` + classification outer/holes),
  - exposé via `pybind11` dans le module `_pwmb_geom`.
- Limite visuelle connue :
  - contours issus d'un raster binaire => rendu naturellement orthogonal/"en escalier",
  - plan d'amelioration UX contours documente dans `docs/53_LOT_K_CONTOURS_QUALITY.md`.
  - etat courant: viewer integre un extracteur subpixel half-grid (Lot K3) en option pipeline.
- Recommandation initiale (alternative) : **OpenCV** en C++
  - `findContours` avec hiérarchie pour outer/holes (RETR_TREE/CCOMP),
  - compression des points (CHAIN_APPROX_SIMPLE).
- Alternatives :
  - marching squares (si on veut des isocontours plus “lisses”, moins adapté au raster orthogonal)
  - vectorisation GIS (raster→polygons) si besoin, mais plus lourd.

### 5.2 Triangulation
- Recommandé : **earcut.hpp (Mapbox)**
  - gère polygons + holes
  - robuste, rapide, très utilisé
- Alternative : Clipper2 (si besoin de booléens/offsetting en plus)

### 5.3 Post-traitements (si nécessaires)
- Simplification : RDP (Douglas–Peucker) ou simplification orthogonale, **en C++**
- Nettoyage : suppression points dupliqués, colinéaires, auto-intersections (si observées)

## 6) Plan de migration (phases)

### Phase A — Baseline et tests de non-régression
1. Constituer un corpus PWMB (petit / plein / troué / haute résolution)
2. Enregistrer métriques actuelles (par couche + global)
3. Mettre en place des checks automatisés : aire, bbox, nb triangles, absence dégénérés

### Phase B — Refactor minimal côté Python (sans changer le comportement)
1. Isoler le “contrat géométrie” (une seule fonction appelée par le pipeline)
2. Encapsuler l’impl actuelle derrière une interface :
   - `GeometryBackend = PythonBackend | CppBackend`
3. Garder les mêmes métriques (BuildMetrics) et points de log

### Phase C — Impl C++ v1 : contours → polygons
1. Créer projet CMake `pwmb_geom_cpp`
2. Impl `extract_polygons(mask)` (extracteur natif C++ ; OpenCV non retenu dans cette itération)
3. Exposer au Python via pybind11
4. Valider : aire/bbox/nb loops/holes vs backend Python

### Phase C-bis — Option OpenCV (lot optionnel)
1. Ajouter un extracteur contours OpenCV en backend alternatif (`findContours` + hierarchie).
2. Selectionner l'implementation via flag/env (ex: `GEOM_CPP_CONTOURS_IMPL=native|opencv`).
3. Verifier la parite semantique avec l'extracteur natif:
   - surfaces (outer-holes),
   - bbox,
   - nombre de loops/hierarchie.
4. Mesurer les performances sur corpus reel et garder l'option la plus robuste.

### Phase D — Impl C++ v2 : polygons → triangles
1. Ajouter earcut.hpp
2. Exposer `triangulate(outers, holes)` (ou directement `build_mesh(mask, params)`)
3. Valider : aire triangulée, indices valides, pas de dégénérés

### Phase E — Buffers contigus / zéro-copie
1. Sorties en NumPy arrays (float32 / uint32)
2. Éviter toutes reconstructions Python de vertices/indices
3. Valider mémoire (profiling) + temps `buffers_ms`

### Phase F — Parallélisation propre
1. Corriger I/O : mmap persistant / accès couche sans ré-ouvrir le fichier
2. Définir stratégie worker :
   - si C++ libère le GIL : ThreadPool possible
   - sinon ProcessPool
3. Batching optionnel (N couches/job) si overhead scheduling

### Phase G — Packaging et CI
1. Construire wheels (Linux) via cibuildwheel
2. Tests : unit + non-régression géométrique sur corpus
3. Benchmarks : seuils (fail si régression > X%)

## 7) Décision d’API (intégration au pipeline)

### 7.1 API recommandée
- `build_layer_mesh(mask, layer_params) -> (vertices, indices)`
  - cache le détail contours/triangulation
  - réduit les allers-retours Python

### 7.2 Mode fallback
- Si `CppBackend` indisponible : fallback `PythonBackend` (dégradé mais fonctionnel)
- Sélection via config/env : `GEOM_BACKEND=cpp|python`

## 8) Risques et parades
- **Différences topologiques** (hiérarchie trous/outer) :
  - normaliser la hiérarchie côté extracteur natif C++, + tests d’aire et mapping stable
- **Orientation / winding** :
  - normaliser CW/CCW côté C++ et documenter
- **Auto-intersections / cas pathologiques** :
  - nettoyage + validation (clipper optionnel)
- **Dépendances lourdes (OpenCV)** :
  - OpenCV n'est pas requis dans l'impl actuelle (extracteur natif),
  - possibilité de variante OpenCV ultérieure si besoin d'interop/robustesse sur corpus élargi.

## 9) Critères d’acceptation
- Visuel : rendu identique (tolérance) sur corpus
- Géométrie : aire/bbox/nb triangles dans tolérance
- Perf : réduction mesurée (targets §2)
- Stabilité : pas de crash, pas de fuite mémoire, reproductible

## 10) Roadmap courte (ordre optimal)
1. Interface backend + baseline
2. C++ contours (extracteur natif ; OpenCV optionnel)
3. Option OpenCV contours (A/B test perf + robustesse)
4. C++ triangulation (earcut)
5. Buffers contigus
6. I/O mmap persistant
7. Parallélisation
8. Qualite percue contours viewer (Lot K: XY stride 100%, downsampling, smoothing)
