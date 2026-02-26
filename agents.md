# Agent Codex — Anycubic Cloud Client + PWMB 3D Viewer (Python, Qt, OpenGL)

## Contexte d’utilisation
Ce fichier définit le cadre d’exécution d’un agent Codex (VS Code) pour un projet **Python** visant à :
1) implémenter un **client Anycubic Cloud** (réplique des appels web UI),
2) intégrer un **viewer PWMB** avec **rendu 3D GPU-first**, build CPU asynchrone et multi-thread/multi-process.

---

## Contraintes générales
- Objectif : **outil utilisable**, stable, prédictible.
- Modifications : **minimales et localisées** (ne pas réécrire l’architecture sans nécessité).
- Priorité : **code** + invariants testables.
- Questionner **uniquement** si une ambiguïté bloque l’implémentation.
- Réponses en **français**.

---

## Objectifs prioritaires
1. Fonctionnement correct sur un compte réel (session valide)
2. Stabilité réseau (timeouts, retry/backoff, pas de crash)
3. Sécurité (zéro fuite de secrets)
4. Lisibilité / maintenabilité (couches nettes, contrats)
5. Viewer PWMB 3D : GPU-first, performant, dégradations propres

---

## Mission
### Cloud
Implémenter un client Python qui accède au cloud via les mêmes endpoints que la web UI.
Fonctions :
- quota (total/used/free + %)
- lister (fichiers)
- infos fichier / gcode info (si dispo)
- télécharger
- uploader
- supprimer
- imprimer (send print order)

### PWMB / 3D
- Lire `.pwmb` (Anycubic) : parse container + décoder couches (`pw0Img`, `pwsImg`).
- Extraire previews (optionnel) + exporter couches en images (debug).
- Construire une représentation 3D (contours/triangles/points), avec **rendu OpenGL**.

---

## Modes d’authentification
### Mode A (prioritaire) : import session
- Entrée : `.har` exporté depuis navigateur.
- Extraction : cookies + tokens.
- Stockage local : `.accloud/session.json` (permissions `0600`).

### Mode B (optionnel) : login direct
- Email/password uniquement si l’API fonctionne sans challenge.

---

## Contraintes de sécurité (obligatoires)
- Ne jamais logger :
  - cookies
  - headers `Authorization`
  - URLs signées complètes (si query sensible)
  - tokens dans JSON
- Redaction systématique :
  - headers sensibles
  - clés sensibles dans payloads/réponses JSON
- Session locale : fichier privé (0600), chemin configurable.

---

## Comportement réseau (obligatoire)
- HTTP : `httpx`.
- Timeouts configurables.
- User-Agent configurable.
- Retry/backoff pour : 429, 5xx, erreurs transitoires.
- Support URLs signées (TTL court).
- Upload : supporter pipeline lock/upload/register/unlock si c’est le modèle observé.

---

## Logs & Observabilité (obligatoire)
### Deux niveaux
1) **console logger** (stdout) : messages runtime (UI, PWMB, 3D)
2) **HTTP log persistant** : fichier `accloud_http.log` + rotation + rétention

### Onglet LOG (Qt)
- Tail de `accloud_http.log` (poll 1s)
- Support rotation/truncate

### Faulthandler
- Activé par défaut côté Qt (désactivable via env)

---

## Interface (GUI) — contraintes
- Application pilotée via GUI (pas de CLI en primaire).
- GUI fine :
  - aucune logique API dans les widgets
  - appels centralisés dans `accloud/client.py` + `accloud/api.py`
- UI gère :
  - loading
  - erreurs exploitables
  - annulation (si possible) opérations longues

---

## Architecture cible (imposée)

### Couche Cloud
- `accloud/`
  - `client.py` : session HTTP + auth + redaction + logs HTTP
  - `api.py` : fonctions haut niveau (quota/list/info/download/upload/delete/print)
  - `models.py` : dataclasses (FileItem, Quota, Printer, GcodeInfo, etc.)
- `session_store.py` : import/export session (HAR + json)
- `utils.py` : retry/backoff, format bytes, truncate, redaction helpers

### Couche PWMB
- `pwmb/`
  - `container.py` : parse FILEMARK + tables
  - `structs.py` : lecture HEADER/MACHINE/LAYERDEF/EXTRA/PREVIEW (best-effort)
  - `decode_pw0.py` : `pw0Img` (16-bit BE, 4+12 RLE, clamp + ignore trailing)
  - `decode_pws.py` : `pwsImg` (RLE byte, AA passes, convention run-length déterminée)
  - `lut.py` : LayerImageColorTable, règle canonique : **index 0 = vide**
  - `export.py` : export preview + export layers
  - `tests/` : vecteurs `cube`, `cube2`, `misteer` + goldens

### Couche 3D (build + GPU)
- `pwmb3d/`
  - `contours.py` : extraction loops depuis mask + simplification
  - `geometry_v2.py` : holes/bridge/triangulation → buffers tri/line/point + ranges
  - `cache.py` : cache contours/geometry + clés d’invalidation explicites
  - `perf.py` : instrumentation build/draw

### GUI Qt
- `gui/` (ou `accloud/gui/`)
  - `app.py` : bootstrap
  - `state.py` : état UI
  - `tabs/`
    - `files_tab.py` : quota/list + cartes fichier + actions
    - `printer_tab.py` : liste imprimantes + statut
    - `log_tab.py` : tail HTTP log
  - `dialogs/`
    - `upload_dialog.py` : upload `.pwmb` + options print/delete
    - `print_dialog.py` : sélection imprimante + `send_print_order`
    - `pwmb3d_dialog.py` : viewer 3D (OpenGL)
  - `widgets/` : composants

---

## Contrats PWMB (à respecter)
### Décodage `pw0Img`
- Unité : mots 16-bit big-endian
- `color_index=(word>>12)&0xF`, `run_len=word&0x0FFF`
- `run_len==0` ⇒ invalide
- clamp dernier run
- ignorer trailing après `W*H`

### LUT / vide
- **Index 0 = vide ⇒ intensity=0** (même si LUT[0] non-nul)
- `NonZeroPixelCount` se compare à `count(index!=0)`

### Décodage `pwsImg`
- Byte : bit7 exposé, bits0..6 reps
- Convention run-length : déterminée par dry-run invariants (pixel_count par passe)
- AA : projection `val=round(255*count/AA)`

### Raster / axes
- row-major, origine haut-gauche
- monde : Y inversé (`Y=(cy - y)*pitch`)

---

## Viewer 3D — GPU-first
- Rendu OpenGL : triangles + lignes + points.
- Thread GL strict : création/upload/draw uniquement dans le thread GL.
- Changement visibilité (cutoff/stride/tri back-to-front) : **ne déclenche pas** rebuild géométrie.

### Pipeline draw (contrat)
1) Fill triangles (si activé)
2) Edges (lignes)
3) Points (debug / mode points)

### Transparence
- Si fill translucide : trier layers visibles back-to-front et dessiner par ranges.

---

## Build CPU — asynchrone + multi-thread / multi-process
- Orchestration : `TaskRunner` (ou équivalent) pour toute tâche longue.
- Annulation : token partagé, checkpoints dans decode/contours/triangulation/assemble.

### Pool
- **ThreadPool** si les opérations lourdes libèrent le GIL (NumPy / libs natives).
- **ProcessPool** si extraction contours / triangulation est Python pur.
  - Workers re-open fichier (mmap local) ; entrée = offsets + params ; sortie = loops/buffers (pas d’image W*H).

---

## Onglet Files (Qt) — contrat
- `refresh()` charge quota + liste.
- Actions : Details / Print / Download / Delete / Upload.
- UploadDialog : accepte `.pwmb`, peut proposer `print_after` + `delete_after`.
- Delete-after-print : suppression auto après fin impression si configuré.

---

## PrintDialog (Qt) — contrat
- Liste imprimantes + filtre online.
- Chargement async gcode info (non bloquant).
- Envoi `send_print_order` avec payload minimal stable (ne pas inventer de champs).

---

## Entrées attendues (source de vérité API)
Le projet doit contenir une source de vérité :
- `api_map.json` (préféré) ou `endpoints.py`.
Doit définir : base URL, endpoints + méthodes, headers requis, schémas request/response (champs essentiels), pagination.

Si manquant :
- ne pas inventer,
- indiquer précisément ce qui manque.

---

## Check-list de validation
### Auth/session
- import HAR OK
- session.json écrit en 0600
- quota OK sans relog

### Cloud
- quota cohérent
- liste stable (pagination)
- download intègre
- upload visible + delete ok
- print order envoyé + statut remonté
- aucun secret en log

### PWMB
- parse `cube/cube2/misteer` OK
- decode couches : taille `W*H`, pas de boucle infinie
- goldens : bbox + nonzero_count + checksum sample

### 3D
- build async (UI non bloquée)
- GPU draw OK (fill/edges/points)
- cutoff/stride sans rebuild
- fallback CPU si GL fail

---

## Politique de modification du code
- Exécuter immédiatement la solution la plus probable.
- Pas de discussion tant que le code :
  - fonctionne,
  - gère les erreurs proprement,
  - n’expose pas de secrets.
- Chaque changement doit être traçable.

### Quand tu rends un changement
- Constat technique
- Actions appliquées
- Validation (comment vérifier)
- Hypothèses (si nécessaire)
- Diff réel + fichiers impactés

### Commits (obligatoire)
- Les **messages de commit doivent être en anglais**.
- Le message (et le découpage éventuel en plusieurs commits) doit être construit **à partir des modifications depuis le dernier commit** :
  - baser le résumé sur `git status`, `git diff --stat HEAD`, et `git diff HEAD`.
  - ne pas inventer : le message doit décrire exactement ce que le diff montre.
- Si plusieurs intentions distinctes apparaissent dans le diff, **split en commits séparés** (cohérents et minimaux).
- Forme : impératif, intention principale (ex: `Fix pw0Img RLE decoding`, `Add GPU draw pipeline contracts`).

Utiliser ce prompt pour générer un message de commit orienté audit/PR review :

```text
Rédige un message de commit Git en anglais, orienté audit/PR review.

Contraintes:
- Titre en anglais, format conventional commit: <type>(<scope>): <summary>
- Corps en puces, concret, sans phrases vagues.
- Mentionner explicitement:
  - changements fonctionnels,
  - robustesse/gestion d’erreurs,
  - tests ajoutés ou modifiés,
  - docs mises à jour.
- Ajouter une ligne finale "Tests:" avec la commande exécutée et le résultat.
- Ajouter une ligne finale "Docs:" avec les fichiers de documentation touchés.
- Ne pas inventer d’éléments non présents dans le diff.

Format attendu:
<type>(<scope>): <summary>

- ...
- ...
- ...

Tests: <commande> (<résultat>)
Docs: <liste de fichiers ou "none">
```

Exemple attendu:

```text
feat(render3d): harden viewer reliability and complete remaining QA tasks

- Add robust OpenGL failure handling in PWMB 3D dialog (init/draw/upload fallback paths).
- Add user-facing build error classification (parse/decode/GL) and "Retry last build" flow.
- Persist viewer settings across sessions (threshold/bin mode/quality/stride/contour-only).
- Enforce strict index mask semantics (color_index != 0) via dedicated PW0 nonzero-mask decoding.
- Add camera-based back-to-front layer ordering for translucent rendering.
- Add integration tests for async viewer build, retry behavior, and renderer-failure UX.
- Add minimal GUI E2E flow: Files -> Viewer -> rebuild -> cutoff/stride.
- Add golden non-regression test (orientation/bbox/checksum) for PWMB geometry outputs.
- Update remaining-task tracker and lot documentation.

Tests: PYTHONPATH=. pytest -q (112 passed)
Docs: RESTE_A_FAIRE.md, docs/52_LOT_J_VIEWER_RELIABILITY_AND_QA.md
```
