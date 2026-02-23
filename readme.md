# Anycubic Cloud Client + PWMB 3D Viewer (Python / Qt / OpenGL)

Project Python qui combines :
1) a **client Anycubic Cloud** (réplication of appels of the web UI),
2) a **viewer PWMB** with **rendering 3D GPU-first** (OpenGL) + build CPU asynchrone (multi-thread / multi-process according to GIL).

> Functional source of truth : `docs/*.md` (ordre recommended: `docs/00_READ_ORDER.md`).

---

## Features

### Cloud (UI + API)
- Quota : total / utilisé / libre (+ %)
- List of files (pagination)
- Details file + gcode info (if dispo)
- Download (URL signée)
- Upload `.pwmb`
- Delete
- Print : envoi d’un “print order” toward a printer online

### PWMB / 3D
- Reading `.pwmb` : parse container (tables/offsets), versions v516/v517+ (best-effort)
- Decoding layers :
 - `pw0Img` : RLE 16-bit BE (4-bit index + 12-bit run), clamp + ignore trailing
 - `pwsImg` : RLE byte, AA passes, convention run-length déterminée via dry-run
- LUT `LayerImageColorTable` :
 - **index 0 = vide** (intensity=0) même if LUT[0] non-nul
- Binarisation : seuil explicite
- Build 3D : contours → holes → bridge → triangulation → buffers
- Rendering OpenGL : triangles / lignes / points
- UI : cutoff/stride/tri back-to-front without rebuild géométrie

---

## Security / privacy (non-negotiable)
- Never log : `Authorization`, tokens, signatures, nonce, secrets, URLs signées complètes if sensibles
- Redaction systématique (headers + JSON)
- Session locale : `session.json` with permissions `0600`
- The logs HTTP persistent doivent être “safe-by-default” (troncature + redaction)

---

## Authentication

### Main mode : HAR import (recommended)
The project not done not “login” to the sens classique : il **importe a session** from a export navigateur.

Workflow :
1. In the navigateur, open DevTools → Network
2. Reload the cloud page
3. Export the network session to the format `.har`
4. Import the `.har` in the app (menu Session → Import HAR)
5. The session is persistée in `session.json`

Notes :
- Session expired ⇒ HAR re-import required
- The tokens extraits are stockés en session (mais never loggés)

---

## Logs & observability

### Files
- Log HTTP persistant : `accloud_http.log` (rotation journalière, rétention)
- Log crash : `accloud_fault.log` (faulthandler)

### UI
- Onglet `LOG` : tail of `accloud_http.log` (poll 1s), support rotation/truncate

---

## Architecture (summary)

### Cloud
- `accloud_core/client.py` : transport HTTP, session, redaction, logging HTTP
- `accloud_core/api.py` : appels haut niveau (quota/list/download/upload/delete/print)
- `accloud_core/models.py` : dataclasses / modèles
- `accloud_core/session_store.py` : import/export session (HAR ↔ session.json)
- `accloud_core/utils.py` : retry/backoff, troncature, redaction

### PWMB
- `pwmb_core/container.py` : parse FILEMARK + adresses tables
- `pwmb_core/structs.py` : reading HEADER/MACHINE/LAYERDEF/EXTRA/PREVIEW (best-effort)
- `pwmb_core/decode_pw0.py` : `pw0Img`
- `pwmb_core/decode_pws.py` : `pwsImg`
- `pwmb_core/lut.py` : LayerImageColorTable + règle “index 0 = vide”
- `pwmb_core/export.py` : export preview + export layers
- `tests/` : vecteurs `cube`, `cube2`, `misteer` + goldens

### 3D (build + GPU)
- `render3d_core/contours.py` : extraction loops + simplification
- `render3d_core/geometry_v2.py` : holes/bridge/triangulation → buffers + ranges
- `render3d_core/cache.py` : cache contours/geometry + keys d’invalidation
- `render3d_core/perf.py` : instrumentation

### GUI Qt
- `app_gui_qt/app.py` : bootstrap
- `app_gui_qt/tabs/` : Files / Printer / Log
- `app_gui_qt/dialogs/` : Upload / Print / PWMB3D viewer

---

## Installation (dev)

Prerequisites :
- Python (version conforme to the project)
- Dependencies listées in `requirements.txt` (or `pyproject.toml`)

Example (à ajuster according to repo) :
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

---

# Version française

# Anycubic Cloud Client + PWMB 3D Viewer (Python / Qt / OpenGL)

Projet Python qui combine :
1) un **client Anycubic Cloud** (réplication des appels de la web UI),
2) un **viewer PWMB** avec **rendu 3D GPU-first** (OpenGL) + build CPU asynchrone (multi-thread / multi-process selon GIL).

> Source de vérité fonctionnelle : `docs/*.md` (ordre recommandé: `docs/00_READ_ORDER.md`).

---

## Fonctionnalités

### Cloud (UI + API)
- Quota : total / utilisé / libre (+ %)
- Liste des fichiers (pagination)
- Détails fichier + gcode info (si dispo)
- Download (URL signée)
- Upload `.pwmb`
- Delete
- Print : envoi d’un “print order” vers une imprimante online

### PWMB / 3D
- Lecture `.pwmb` : parse container (tables/offsets), versions v516/v517+ (best-effort)
- Décodage layers :
  - `pw0Img` : RLE 16-bit BE (4-bit index + 12-bit run), clamp + ignore trailing
  - `pwsImg` : RLE byte, AA passes, convention run-length déterminée via dry-run
- LUT `LayerImageColorTable` :
  - **index 0 = vide** (intensity=0) même si LUT[0] non-nul
- Binarisation : seuil explicite
- Construction 3D : contours → holes → bridge → triangulation → buffers
- Rendu OpenGL : triangles / lignes / points
- UI : cutoff/stride/tri back-to-front sans rebuild géométrie

---

## Sécurité / confidentialité (non négociable)
- Ne jamais logger : `Authorization`, tokens, signatures, nonce, secrets, URLs signées complètes si sensibles
- Redaction systématique (headers + JSON)
- Session locale : `session.json` avec permissions `0600`
- Les logs HTTP persistent doivent être “safe-by-default” (troncature + redaction)

---

## Authentification

### Mode principal : import HAR (recommandé)
Le projet ne fait pas “login” au sens classique : il **importe une session** depuis un export navigateur.

Workflow :
1. Dans le navigateur, ouvrir DevTools → Network
2. Recharger la page cloud
3. Exporter la session réseau au format `.har`
4. Importer le `.har` dans l’app (menu Session → Import HAR)
5. La session est persistée dans `session.json`

Notes :
- Session expirée ⇒ réimport HAR nécessaire
- Les tokens extraits sont stockés en session (mais jamais loggés)

---

## Logs & observabilité

### Fichiers
- Log HTTP persistant : `accloud_http.log` (rotation journalière, rétention)
- Log crash : `accloud_fault.log` (faulthandler)

### UI
- Onglet `LOG` : tail de `accloud_http.log` (poll 1s), support rotation/truncate

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
- `tests/` : vecteurs `cube`, `cube2`, `misteer` + goldens

### 3D (build + GPU)
- `render3d_core/contours.py` : extraction loops + simplification
- `render3d_core/geometry_v2.py` : holes/bridge/triangulation → buffers + ranges
- `render3d_core/cache.py` : cache contours/geometry + clés d’invalidation
- `render3d_core/perf.py` : instrumentation

### GUI Qt
- `app_gui_qt/app.py` : bootstrap
- `app_gui_qt/tabs/` : Files / Printer / Log
- `app_gui_qt/dialogs/` : Upload / Print / PWMB3D viewer

---

## Installation (dev)

Pré-requis :
- Python (version conforme au projet)
- Dépendances listées dans `requirements.txt` (ou `pyproject.toml`)

Exemple (à ajuster selon repo) :
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
