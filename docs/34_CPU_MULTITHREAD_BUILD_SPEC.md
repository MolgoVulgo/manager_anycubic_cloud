### Objectif
Accélérer le build CPU sans casser le déterminisme ni l’intégration OpenGL.

### Contraintes
- Thread GL : upload/draw uniquement.
- CPU : peut être parallélisé **si** les opérations libèrent le GIL (NumPy/algos C) ; sinon, préférer un modèle multi-process.

### Modèle d’exécution (contrat)
Le runtime choisit **une** stratégie selon la nature des fonctions utilisées :

1) **ThreadPool** (préféré si GIL libéré)
- Décodage (NumPy) : généralement OK.
- Nettoyage morpho / contours / triangulation : OK uniquement si impl C/C++ (ex libs natives).

2) **ProcessPool** (fallback réaliste si Python pur)
- Obligatoire si la triangulation/extraction loops est majoritairement Python.
- Contrat : les workers ouvrent le fichier eux-mêmes (mmap local) et reçoivent uniquement :
  - `path`, `layer_index`, `DataAddress`, `DataLength`, `W,H`, params.
- Résultats renvoyés : loops simplifiées / buffers par layer (éviter de renvoyer une image `W*H`).

> Le choix (thread vs process) doit être **configurable** (flag) et loggé.

### Phases
**A — Parse (single-thread)**
- Lire container + tables minimales.

**B — Build contours (pool, 1 job = 1 layer)**
- decode → mask → loops → simplify → world coords
- sortie : `LayerContours(i)` + stats.

**C — Budgets/LOD (single-thread)**
- appliquer `max_layers/max_vertices/max_xy_stride`
- décider les couches gardées / stride.

**D — Build geometry V2 (pool, 1 job = 1 layer)**
- outer/holes + containment
- bridge
- triangulation
- génération tri/line/point buffers pour la couche

**E — Assemble (single-thread)**
- concat buffers dans un ordre stable (par index layer)
- construire ranges par layer.

### Workers
- `workers = min(physical_cores, 8)`
- Ne jamais conserver les images `W*H` au-delà du job.

### Erreurs
- Couche invalide : skip + log.
- Erreur pool globale : fail build, remonter à l’UI.

---

