# Anycubic Cloud Client + PWMB 3D Viewer (Python / Qt / OpenGL)

Projet Python qui combine :
1) un **client Anycubic Cloud** (réplication des appels de la web UI),
2) un **viewer PWMB** avec **rendu 3D GPU-first** (OpenGL) + build CPU asynchrone (multi-thread / multi-process selon GIL).

> Source de vérité fonctionnelle : `docs/pwmb/*` (PWMB + 3D) et `docs/accloud/*` (session/logs/files/print).

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
- Ne jamais logger : cookies, `Authorization`, tokens, secrets, URLs signées complètes si sensibles
- Redaction systématique (headers + JSON)
- Session locale : `.accloud/session.json` avec permissions `0600`
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
5. La session est persistée dans `.accloud/session.json`

Notes :
- Session expirée ⇒ réimport HAR nécessaire
- Cookies seuls peuvent suffire selon cas ; tokens si présents sont stockés en session (mais jamais loggés)

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
- `accloud/client.py` : transport HTTP, session, redaction, logging HTTP
- `accloud/api.py` : appels haut niveau (quota/list/download/upload/delete/print)
- `accloud/models.py` : dataclasses / modèles
- `accloud/session_store.py` : import/export session (HAR ↔ session.json)
- `accloud/utils.py` : retry/backoff, troncature, redaction

### PWMB
- `pwmb/container.py` : parse FILEMARK + adresses tables
- `pwmb/structs.py` : lecture HEADER/MACHINE/LAYERDEF/EXTRA/PREVIEW (best-effort)
- `pwmb/decode_pw0.py` : `pw0Img`
- `pwmb/decode_pws.py` : `pwsImg`
- `pwmb/lut.py` : LayerImageColorTable + règle “index 0 = vide”
- `pwmb/export.py` : export preview + export layers
- `pwmb/tests/` : vecteurs `cube`, `cube2`, `misteer` + goldens

### 3D (build + GPU)
- `pwmb3d/contours.py` : extraction loops + simplification
- `pwmb3d/geometry_v2.py` : holes/bridge/triangulation → buffers + ranges
- `pwmb3d/cache.py` : cache contours/geometry + clés d’invalidation
- `pwmb3d/perf.py` : instrumentation

### GUI Qt
- `gui/app.py` (ou `accloud/gui/app.py`) : bootstrap
- `gui/tabs/` : Files / Printer / Log
- `gui/dialogs/` : Upload / Print / PWMB3D viewer

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
