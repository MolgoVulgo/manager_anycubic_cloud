# Plan de mise en place - Anycubic Cloud Client + PWMB 3D Viewer

## 0) Analyse synthetique des documents

### Sources analysees
- `readme.md`
- `agents.md`
- Tous les fichiers dans `docs/`

### Contraintes majeures identifiees
- Architecture imposee en couches: `accloud/`, `pwmb/`, `pwmb3d/`, `gui/`.
- Securite non negociable: aucune fuite de secrets dans les logs, redaction systematique, session `0600`.
- Pipeline PWMB canonique: container -> structs -> decode layer -> binarisation explicite -> contours -> geometrie -> rendu.
- Contrats de decode stricts:
  - `pw0Img`: mots 16-bit big-endian, `run_len==0` invalide, clamp trailing.
  - `pwsImg`: choix deterministe `C0/C1`, AA multi-passes, projection monotone vers `uint8`.
  - LUT: `index 0 = vide` meme si LUT[0] non nul.
- Rendu GPU-first: OpenGL sur thread GL uniquement, no rebuild CPU sur simple changement de visibilite.
- Build CPU asynchrone + annulation + choix `ThreadPool/ProcessPool` selon GIL.
- Tests attendus: vecteurs stables (`cube`, `cube2`, `misteer`), goldens, checks orientation/axes.
- Logging attendu sur 2 canaux: console runtime + fichier HTTP persistant avec rotation/retenue.

### Point d attention de cadrage
- `api_map.json` (ou `endpoints.py`) est cite comme source de verite API, mais n est pas present dans le depot actuel.

---

## 1) Mise en place du squelette de l app

### 1.1 Initialiser la structure projet
- Creer l arborescence cible:
  - `accloud/` (`client.py`, `api.py`, `models.py`, `session_store.py`, `utils.py`)
  - `pwmb/` (`container.py`, `structs.py`, `decode_pw0.py`, `decode_pws.py`, `lut.py`, `export.py`)
  - `pwmb3d/` (`contours.py`, `geometry_v2.py`, `cache.py`, `perf.py`)
  - `gui/` (`app.py`, `state.py`, `tabs/`, `dialogs/`, `widgets/`)
  - `tests/` (unit, integration, e2e, goldens)
- Initialiser le packaging Python (`pyproject.toml`) et les dependances minimales.

### 1.2 Poser les contrats techniques
- Definir les modeles/datatypes centraux:
  - `PwmbDocument`, `LayerDef`, `PwmbContourStack`, `PwmbContourGeometry`
  - `Quota`, `FileItem`, `Printer`, `GcodeInfo`, `SessionData`
- Definir les interfaces/stubs:
  - transport HTTP + redaction
  - parseur/decodeur PWMB
  - builder geometrie
  - renderer GL
  - orchestrateur async (`TaskRunner`) avec annulation/progress.

### 1.3 Base d execution
- Entrypoint GUI (`gui/app.py`) + configuration (env, chemins, logs).
- Gestion des erreurs globales + faulthandler.
- Configuration centralisee (timeouts, user-agent, retries, mode pool, etc.).

### Definition of Done - Etape 1
- Le projet demarre avec une fenetre GUI minimale.
- L architecture de dossiers/fichiers est en place.
- Les contrats (types/interfaces) compilent/importent sans logique metier complete.

---

## 2) Mise en place de l interface (design uniquement, boutons non fonctionnels)

### 2.1 Shell GUI
- Construire layout principal avec tabs:
  - `Files`
  - `Printer`
  - `Log`
- Ajouter les dialogs:
  - Upload
  - Print
  - Viewer PWMB3D

### 2.2 Design system UI
- Definir style guide: spacing, typo, couleurs, etats (normal/loading/error/disabled).
- Creer composants reutilisables (`widgets/`): cartes fichier, badges statut, toolbar actions.
- Tous les boutons sont branches sur handlers "stub" (message "not implemented").

### 2.3 Etats UX sans backend
- Simuler les etats:
  - loading
  - empty state
  - erreur utilisateur exploitable
  - donnees factices
- Preparer les placeholders pour cutoff/stride/qualite/tri back-to-front.

### Definition of Done - Etape 2
- L interface complete est navigable.
- Le design est valide sur toutes les vues principales.
- Aucune action metier reelle n est executee.

---

## 3) Mise en place des fonctionnalites (en plusieurs phases)

### 3.1 Phase A - Auth/session et base Cloud
- Import HAR -> extraction cookies/tokens -> persist `.accloud/session.json` en `0600`.
- Client HTTP `httpx` avec timeouts, retry/backoff, user-agent configurable.
- Redaction securisee des logs HTTP des la premiere requete.

### 3.2 Phase B - Features Cloud lecture
- Quota.
- Liste fichiers avec pagination.
- Details fichier + gcode info (si dispo).
- Download via URL signee (gestion TTL/cas expires).

### 3.3 Phase C - Features Cloud ecriture
- Upload `.pwmb` (pipeline lock/upload/register/unlock si observe).
- Delete fichier.
- Send print order (payload minimal stable) + remontee statut.

### 3.4 Phase D - PWMB parsing + decoding
- Parse container (`FILEMARK`, adresses, bornes).
- Parse structs (`HEADER`, `MACHINE`, `LAYERDEF`, LUT, tables optionnelles).
- Decoder `pw0Img` et `pwsImg` selon contrats docs.
- Exposer decode layer + export debug PNG.

### 3.5 Phase E - Pipeline 3D CPU
- Binarisation explicite (`index_strict` et `threshold`).
- Extraction contours/holes + simplification.
- Triangulation + generation buffers tri/line/point.
- Orchestration async + cancel + progress stages normalises.

### 3.6 Phase F - Rendu GPU + interactions
- Upload buffers sur thread GL uniquement.
- Draw pipeline canonique (fill -> edges -> points).
- Visibilite dynamique (cutoff/stride/sort back-to-front) sans rebuild CPU.
- Fallback CPU si echec init/upload GL.

### 3.7 Phase G - Cache/perf
- Cache contours + geometry avec cles d invalidation explicites.
- Instrumentation perf CPU/GPU (`parse_ms`, `decode_ms_total`, `upload_ms`, `draw_ms`, etc.).

### Definition of Done - Etape 3
- Parcours complet fonctionnel: session -> cloud -> ouverture PWMB -> build 3D -> rendu.
- Respect des contrats critiques (decode, raster/axes, GL-thread, no-secret-logs).

---

## 4) Mise en place des tests pour eviter les regressions

### 4.1 Tests unitaires
- `accloud/utils.py`: redaction, truncation, retry policy.
- `pwmb/decode_pw0.py`: run_len, clamp, trailing, endian.
- `pwmb/decode_pws.py`: selection convention `C0/C1`, AA projection.
- `pwmb/lut.py`: contrainte `index 0 = vide`.

### 4.2 Tests integration
- API cloud via mocks/reponses enregistrees (sans secrets).
- Import HAR -> session JSON `0600`.
- Upload/download/delete/print avec cas erreurs transitoires.

### 4.3 Tests goldens PWMB
- Vecteurs: `cube`, `cube2`, `misteer`.
- Assertions decode:
  - taille `W*H`
  - `nonzero_count`
  - `bbox_px`
  - checksum echantillonne stable
- Tests orientation axes (pas de flip/mirror/swap XY).

### 4.4 Tests 3D + rendu
- Build geometry deterministe (ranges/layers stables).
- Verification "no rebuild" lors de changement cutoff/stride.
- Smoke test renderer + fallback CPU.

### 4.5 CI anti-regression
- Pipeline CI:
  - lint/type-check
  - unit + integration + goldens
  - seuils perf basiques (non bloquants au debut puis durcis).

### Definition of Done - Etape 4
- Les tests critiques tournent automatiquement en CI.
- Une regression decode/axes/cache/rendu est detectee avant merge.

---

## 5) Mise en place des logs (plusieurs levels)

### 5.1 Politique de niveaux
- `DEBUG`: details techniques (decode/perf/cache) sans secret.
- `INFO`: progression normale (sync, build, draw).
- `WARNING`: degradations/fallback/retentatives.
- `ERROR`: echec operationnel recuperable.
- `CRITICAL`: crash imminent/corruption etat.

### 5.2 Canaux de logs
- Console runtime (UI + PWMB + 3D).
- Fichier HTTP persistant `accloud_http.log` (rotation journaliere + retention).
- Fichier crash `accloud_fault.log` via faulthandler.

### 5.3 Redaction et hygiene
- Filtre global de redaction (headers + JSON + query params sensibles).
- Interdiction absolue de logger cookies/tokens/Authorization/signatures completes.
- Format stable avec correlation id (requete/tache) pour tracer un flux.

### 5.4 Exposition UI
- Onglet `Log` avec tail 1s + support rotation/truncate.
- Filtres niveau/module pour debug terrain.

### Definition of Done - Etape 5
- Logs exploitables en prod/dev, sans fuite de secret.
- Niveau de verbosite configurable sans modifier le code.

---

## Ordre d execution recommande
1. Etape 1 (squelette)  
2. Etape 2 (design UI statique)  
3. Etape 3 (fonctionnalites par phases A -> G)  
4. Etape 5 (logs) en parallele des phases 3A/3B, puis durcissement final  
5. Etape 4 (tests) des le debut, puis completion avant stabilisation finale

Note: meme si listee en #4, la strategie tests doit demarrer pendant l Etape 1 pour limiter la dette technique.
