# Anycubic Cloud Client + PWMB 3D Viewer

> This repository is the legacy Python implementation.
> **V3 is now available here:** https://github.com/MolgoVulgo/anycubic-cloud-manager-v3
> The main V3 change is the migration from **Python to C++** to improve performance, runtime efficiency, and maintainability on the 3D/rendering pipeline.
> Core features remain the same between this version and V3.

This project combines:
1) an **Anycubic Cloud client** (replaying the web UI calls),
2) a **PWMB viewer** with **GPU-first 3D rendering** (OpenGL) and an **async CPU build pipeline** (threads/processes depending on the GIL and backend).

> Functional source of truth: `docs/*.md` (recommended order: `docs/00_READ_ORDER.md`).

---

## Features

### Cloud (UI + API)
- Quota: total / used / free (+ %)
- File list (pagination)
- File details + gcode info (when available)
- Download (signed URL)
- Upload `.pwmb`
- Delete
- Print: sends a “print order” to an online printer

### PWMB / 3D
- Read `.pwmb`: container parsing (tables/offsets), versions v516/v517+ (best-effort)
- Layer decoding:
  - `pw0Img`: RLE 16-bit BE (4-bit index + 12-bit run), clamp + ignore trailing
  - `pwsImg`: RLE byte, AA passes, run-length convention determined via dry-run
- LUT `LayerImageColorTable`:
  - **index 0 = empty** (intensity=0) even if LUT[0] is non-zero
- Binarization: explicit threshold
- 3D build: contours → holes → bridge → triangulation → buffers
- OpenGL rendering: triangles / lines / points
- UI: cutoff/stride/tri back-to-front **without rebuilding geometry**

---

## Security / privacy (non-negotiable)
- Never log: `Authorization`, tokens, signatures, nonces, secrets, full signed URLs
- Systematic redaction (headers + JSON)
- Local session: `session.json` with permissions `0600`
- HTTP logs are “safe-by-default” (bounded + truncated + redacted)

---

## Authentication

### Main mode: HAR import (recommended)
The project does not “login” in the classic way: it **imports a session** from a browser export.

Workflow:
1. In the browser, open DevTools → Network
2. Reload the cloud page
3. Export the network session as `.har`
4. Import the `.har` in the app (Session → Import HAR)
5. The session is persisted in `session.json`

Notes:
- Session expired ⇒ HAR re-import required
- Extracted tokens are stored in session, but never logged

---

## Logs & observability

This project follows a **strict logging contract**: see `docs/999_LOG_GUIDE.md`.

### Log directory
- Default: `./.accloud/logs/`
- Override: `ACCLOUD_LOG_DIR=/path`

### Log files (JSONL)
- App (everything except HTTP): `accloud_app.log` (+ rotations)
- HTTP transport only: `accloud_http.log` (+ rotations)
- Render/3D subset: `accloud_render3d.log` (+ rotations)
- Crash: `accloud_fault.log` (faulthandler)

### Rotation / retention / compression
- Rotation by size (default 10 MiB): `ACCLOUD_LOG_MAX_BYTES=10485760`
- Keep N backups (default 5): `ACCLOUD_LOG_BACKUPS=5`
- Backups are gzip-compressed: `ACCLOUD_LOG_COMPRESS=1`, `ACCLOUD_LOG_COMPRESS_LEVEL=6`

### Correlation
- Every user-level operation carries an `op_id` propagated across async jobs.

---

## Architecture (summary)

### Cloud
- `accloud_core/client.py`: HTTP transport, session, redaction, HTTP logging
- `accloud_core/api.py`: high-level calls (quota/list/download/upload/delete/print)
- `accloud_core/models.py`: dataclasses / models
- `accloud_core/session_store.py`: import/export session (HAR ↔ session.json)
- `accloud_core/utils.py`: retry/backoff, truncation, redaction

### PWMB
- `pwmb_core/container.py`: FILEMARK parsing + table addresses
- `pwmb_core/structs.py`: read HEADER/MACHINE/LAYERDEF/EXTRA/PREVIEW (best-effort)
- `pwmb_core/decode_pw0.py`: `pw0Img`
- `pwmb_core/decode_pws.py`: `pwsImg`
- `pwmb_core/lut.py`: LayerImageColorTable + “index 0 = empty” rule
- `pwmb_core/export.py`: export preview + export layers
- `tests/`: vectors + goldens

### 3D (build + GPU)
- `render3d_core/contours.py`: loop extraction + simplification
- `render3d_core/geometry_v2.py`: holes/bridge/triangulation → buffers + ranges
- `render3d_core/cache.py`: cache contours/geometry + invalidation keys
- `render3d_core/perf.py`: instrumentation

### GUI Qt
- `app_gui_qt/app.py`: bootstrap + wiring callbacks
- `app_gui_qt/tabs/`: Files / Printer / Log
- `app_gui_qt/dialogs/`: Upload / Print / PWMB3D viewer

---

## Installation (dev)

Prerequisites:
- Python (project version)
- Dependencies listed in `requirements.txt` (or `pyproject.toml`)

Example (adjust to your repo layout):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Run (dev)

Entry point (repo v2): `app_gui_qt/app.py`.

Examples (adjust to your packaging):
```bash
python app_gui_qt/app.py
# or
python -m app_gui_qt.app
```

Typical workflow:
1. Import HAR session
2. Refresh files
3. Open a `.pwmb` in the 3D viewer

---

## Development method

This application is developed in **vibe coding** with **Codex 5.3**:
- specs/docs first (`docs/*.md`),
- deterministic generation in “waves” (small deltas + validation),
- instrumentation and strict contracts (logs, errors, invariants).

---

## Credits

- **UVtools**: reference and inspiration for PWMB format handling and ecosystem compatibility.
- Anycubic Photon Workshop: the official tool producing/consuming `.pwmb` files.

---

# Version française

# Anycubic Cloud Client + PWMB 3D Viewer (Python / Qt / OpenGL)

Projet Python qui combine :
1) un **client Anycubic Cloud** (rejoue les appels de la web UI),
2) un **viewer PWMB** avec **rendu 3D GPU-first** (OpenGL) et **pipeline CPU asynchrone** (threads/process selon le GIL et le backend).

> Source de vérité fonctionnelle : `docs/*.md` (ordre recommandé : `docs/00_READ_ORDER.md`).

---

## Fonctionnalités

### Cloud (UI + API)
- Quota : total / utilisé / libre (+ %)
- Liste des fichiers (pagination)
- Détails fichier + infos gcode (si dispo)
- Download (URL signée)
- Upload `.pwmb`
- Delete
- Print : envoi d’un “print order” vers une imprimante online

### PWMB / 3D
- Lecture `.pwmb` : parsing container (tables/offsets), versions v516/v517+ (best-effort)
- Décodage des couches :
  - `pw0Img` : RLE 16-bit BE (index 4-bit + run 12-bit), clamp + ignore trailing
  - `pwsImg` : RLE byte, passes AA, convention run-length déterminée via dry-run
- LUT `LayerImageColorTable` :
  - **index 0 = vide** (intensity=0) même si LUT[0] est non-nul
- Binarisation : seuil explicite
- Construction 3D : contours → holes → bridge → triangulation → buffers
- Rendu OpenGL : triangles / lignes / points
- UI : cutoff/stride/tri back-to-front **sans rebuild géométrie**

---

## Sécurité / confidentialité (non négociable)
- Ne jamais logger : `Authorization`, tokens, signatures, nonce, secrets, URLs signées complètes
- Redaction systématique (headers + JSON)
- Session locale : `session.json` avec permissions `0600`
- Logs HTTP “safe-by-default” (bornés + troncature + redaction)

---

## Authentification

### Mode principal : import HAR (recommandé)
Le projet ne fait pas un “login” classique : il **importe une session** depuis un export navigateur.

Workflow :
1. Dans le navigateur, ouvrir DevTools → Network
2. Recharger la page cloud
3. Exporter la session réseau au format `.har`
4. Importer le `.har` dans l’app (Session → Import HAR)
5. La session est persistée dans `session.json`

Notes :
- Session expirée ⇒ réimport HAR nécessaire
- Les tokens extraits sont stockés en session (mais jamais loggés)

---

## Logs & observabilité

Ce projet suit un **contrat de logs strict** : voir `docs/999_LOG_GUIDE.md`.

### Répertoire logs
- Default : `./.accloud/logs/`
- Override : `ACCLOUD_LOG_DIR=/chemin`

### Fichiers (JSONL)
- App (tout sauf HTTP) : `accloud_app.log` (+ rotations)
- HTTP transport uniquement : `accloud_http.log` (+ rotations)
- Rendu/3D (sous-ensemble) : `accloud_render3d.log` (+ rotations)
- Crash : `accloud_fault.log` (faulthandler)

### Rotation / rétention / compression
- Rotation par taille (default 10 MiB) : `ACCLOUD_LOG_MAX_BYTES=10485760`
- Conserver N backups (default 5) : `ACCLOUD_LOG_BACKUPS=5`
- Backups compressés gzip : `ACCLOUD_LOG_COMPRESS=1`, `ACCLOUD_LOG_COMPRESS_LEVEL=6`

### Corrélation
- Toute opération utilisateur porte un `op_id` propagé dans les jobs asynchrones.

---

## Architecture (résumé)

### Cloud
- `accloud_core/client.py` : transport HTTP, session, redaction, logging HTTP
- `accloud_core/api.py` : appels haut niveau (quota/list/download/upload/delete/print)
- `accloud_core/models.py` : dataclasses / modèles
- `accloud_core/session_store.py` : import/export session (HAR ↔ session.json)
- `accloud_core/utils.py` : retry/backoff, troncature, redaction

### PWMB
- `pwmb_core/container.py` : parse FILEMARK + adresses tables
- `pwmb_core/structs.py` : lecture HEADER/MACHINE/LAYERDEF/EXTRA/PREVIEW (best-effort)
- `pwmb_core/decode_pw0.py` : `pw0Img`
- `pwmb_core/decode_pws.py` : `pwsImg`
- `pwmb_core/lut.py` : LayerImageColorTable + règle “index 0 = vide”
- `pwmb_core/export.py` : export preview + export layers
- `tests/` : vecteurs + goldens

### 3D (build + GPU)
- `render3d_core/contours.py` : extraction loops + simplification
- `render3d_core/geometry_v2.py` : holes/bridge/triangulation → buffers + ranges
- `render3d_core/cache.py` : cache contours/geometry + clés d’invalidation
- `render3d_core/perf.py` : instrumentation

### GUI Qt
- `app_gui_qt/app.py` : bootstrap + wiring callbacks
- `app_gui_qt/tabs/` : Files / Printer / Log
- `app_gui_qt/dialogs/` : Upload / Print / PWMB3D viewer

---

## Installation (dev)

Pré-requis :
- Python (version du projet)
- Dépendances listées dans `requirements.txt` (ou `pyproject.toml`)

Exemple (à ajuster selon repo) :
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Exécution (dev)

Point d’entrée (repo v2) : `app_gui_qt/app.py`.

Exemples (à ajuster selon packaging) :
```bash
python app_gui_qt/app.py
# ou
python -m app_gui_qt.app
```

Workflow typique :
1. Import HAR session
2. Refresh files
3. Ouvrir un `.pwmb` dans le viewer 3D

---

## Méthode de développement

Cette app est développée en **vibe coding** avec **Codex 5.3** :
- specs/docs d’abord (`docs/*.md`),
- génération déterministe par “vagues” (petits incréments + validation),
- instrumentation et contrats stricts (logs, erreurs, invariants).

---

## Crédits

- **UVtools** : référence et inspiration pour la compréhension du format PWMB et la compatibilité écosystème.
- Anycubic Photon Workshop : outil officiel qui produit/consomme les fichiers `.pwmb`.
