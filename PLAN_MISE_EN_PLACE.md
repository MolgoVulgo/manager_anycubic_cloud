# Implementation plan - Anycubic Cloud Client + PWMB 3D Viewer

## Tracking update (status to the 2026-02-22)

### Verification scope
- Plan compare with the code actuel in `accloud_core/`, `pwmb_core/`, `render3d_core/`, `app_gui_qt/` and `tests/`.
- Validation executee: `PYTHONPATH=. pytest -q` -> `29 passed`.

### Overall status
- Etape 1 (squelette): `DONE`.
- Etape 2 (interface): `PARTIAL ADVANCED`.
- Etape 3 (features): `PARTIAL`.
- Etape 4 (tests): `PARTIAL`.
- Etape 5 (logs): `PARTIAL ADVANCED`.

---

## 1) App skeleton setup

### Status
`DONE`

### Plan vs code comparison
- Structure repo en layers conforme a `docs/02_REPO_LAYOUT.md`:
 - `accloud_core/`
 - `pwmb_core/`
 - `render3d_core/`
 - `app_gui_qt/`
 - `tests/`
- Packaging and dependencies presentes (`pyproject.toml`).
- Entree d execution GUI en place (`app_gui_qt/app.py`).
- Configuration centralisee en place (`accloud_core/config.py`).
- Types centraux presents:
 - Cloud: `Quota`, `FileItem`, `Printer`, `GcodeInfo`, `SessionData`
 - PWMB: `PwmbDocument`, `LayerDef`
 - 3D: `PwmbContourStack`, `PwmbContourGeometry`
- Base async presente via `render3d_core/task_runner.py` (squelette usable).

### Definition of Done - Step 1 (status)
- Window GUI demarre: `OK`.
- Architecture folders/files en place: `OK`.
- Contrats/types importables: `OK`.

---

## 2) Interface setup (design + etats UX)

### Status
`PARTIAL ADVANCED`

### Plan vs code comparison
- Shell GUI en place:
 - tabs `Files`, `Printer`, `Log`.
 - dialogs `Upload`, `Print`, `PWMB3D`, `Session Settings`.
- Design system of base en place (`app_gui_qt/theme.py`, `app_gui_qt/widgets/`).
- Etats UX actifs:
 - loading/error/empty states on Files and Printer.
 - fallback cache startup for files/printers.
 - thumbnails asynchrones with cache local.
- Onglet `Log` fonctionnel with tail 1s + filtres niveau/module + search texte.

### Remaining work
- Actions metier GUI encore en stub:
 - Files: `Upload`, `Delete`, `Print`, `Download`.
 - Dialogs Upload/Print: actions metier non branchees.
 - Viewer PWMB3D: viewport and commandes encore placeholder.

### Definition of Done - Step 2 (status)
- Interface navigable: `OK`.
- Design principal en place: `OK`.
- "Boutons non fonctionnels" conserve for a partie of actions: `PARTIAL`.

---

## 3) Feature implementation (phases A -> G)

### 3.1 Phase A - Auth/session and base Cloud
Status: `DONE`

- Import HAR actif (`extract_tokens_from_har`) with extraction from:
 - reponses JSON,
 - headers token,
 - query fallback.
- Session load/save/merge en place (`accloud_core/session_store.py`).
- Ecriture session en `0600`.
- Client HTTP `httpx` with retries/backoff/timeouts (`accloud_core/client.py`).
- Redaction securisee active of logs HTTP.
- Recovery auth en place on `401/403` with relogin `loginWithAccessToken` puis replay.

### 3.2 Phase B - Features Cloud reading
Status: `DONE`

- Quota: implemente (`get_quota`).
- List files + mapping large champs cloud: implemente (`list_files`).
- Details file: implemente (`get_file_details`).
- Gcode info: implemente (`get_gcode_info`).
- Download via URL signee: implemente (`download_file`).

### 3.3 Phase C - Features Cloud ecriture
Status: `PARTIAL`

- Backend API en place:
 - upload `.pwmb` lock/upload/register/unlock (`upload_file`),
 - delete (`delete_file`),
 - print order (`send_print_order`).
- List printers cloud en place (`list_printers`) and branchee a l onglet Printer.
- Reste cote UI:
 - appels metier Upload/Delete/Print/Download not encore connectes to the boutons.
 - dialogs Upload/Print restent majoritairement stubs.

### 3.4 Phase D - PWMB parsing + decoding
Status: `DONE`

- Parse FILEMARK/adresses/tables (`pwmb_core/container.py`).
- Parse HEADER/MACHINE/LAYERDEF (`pwmb_core/structs.py`).
- Decode `pw0Img` conforme (16-bit big-endian, run_len 0 invalide, clamp trailing).
- Decode `pwsImg` conforme (selection convention `C0/C1`, AA multi-pass, projection uint8).
- LUT with regle `index 0 = vide`.
- Decode layer + export PNG debug en place.

### 3.5 Phase E - Pipeline 3D CPU
Status: `A FAIRE`

- `render3d_core/contours.py`: `NotImplementedError`.
- `render3d_core/geometry_v2.py`: `NotImplementedError`.
- Not of pipeline complet binarisation -> contours -> triangulation -> buffers.

### 3.6 Phase F - Rendering GPU + interactions
Status: `A FAIRE`

- Not of renderer GPU operationnel.
- Not of gestion GL-thread/upload/draw pipeline.
- Viewer UI encore placeholder.

### 3.7 Phase G - Cache/perf
Status: `PARTIAL MINIMAL`

- Structures presentes:
 - `render3d_core/cache.py` (cles + caches memoire),
 - `render3d_core/perf.py` (dataclasses metrics).
- Mais not d integration reelle on a pipeline 3D effectif.

### Definition of Done - Step 3 (status)
- Parcours complet vise (session -> cloud -> ouverture PWMB -> build 3D -> rendering): `NON ATTEINT`.
- Parcours disponible aujourd hui:
 - session -> cloud -> files/printers -> metadata -> cache local: `ATTEINT`.
 - decode PWMB unitaire/integration without rendering 3D: `ATTEINT`.

---

## 4) Setup en place of tests for eviter the regressions

### Status
`PARTIAL`

### Plan vs code comparison
- Unitaires presents:
 - redaction logs (token/signature/nonce, incluant `XX-*`),
 - decode `pw0` and `pws`,
 - LUT index 0.
- Integration presents:
 - flows cloud (quota/files/download/signature/auth recovery 401/403),
 - import HAR + session JSON `0600`,
 - parsing/decoding PWMB synthetic + export PNG.
- Status execution locale: `29 passed`.

### Remaining work
- `tests/e2e/`: not of vrais tests workflow/UI.
- `tests/goldens/`: not of vecteurs `cube/cube2/misteer` integres.
- Aucun test 3D CPU/GPU (contours/geometrie/no-rebuild/fallback), car pipeline non implemente.
- If execution brute without `PYTHONPATH=.`, the collecte echoue (packaging test a finaliser).

### Definition of Done - Step 4 (status)
- Couverture critique cloud+decode of base: `PARTIELLEMENT ATTEINT`.
- Couverture anti-regression 3D/goldens/e2e: `NON ATTEINT`.

---

## 5) Setup en place of logs (plusieurs levels)

### Status
`PARTIAL ADVANCED`

### Plan vs code comparison
- Niveaux logs utilises (`DEBUG/INFO/WARNING/ERROR`).
- Canal file principal with rotation journaliere + retention (`TimedRotatingFileHandler`).
- Crash log via faulthandler (`accloud_fault.log`) conditionnel a the config.
- Hygiene security active:
 - redaction headers/json/query for `token/signature/nonce` and variantes `XX-*`.
 - logs HTTP not montrent not the secrets bruts.
- Correlation HTTP of base via `X-Request-Id`.
- Exposition UI en place via onglet `Log` (tail 1s, filtres, search).

### Remaining work
- Etendre correlation id to the dela of the transport HTTP (jobs UI/3D futurs).
- Ajouter of tests dedies of non-regression on format/rules of logs.

### Definition of Done - Step 5 (status)
- Logs exploitables without fuite evidente of secrets: `ATTEINT`.
- Durcissement complet observabilite multi-pipeline: `PARTIAL`.

---

## Backlog prioritaire remaining (ordre recommande)

1. Implementer the phase 3E (pipeline 3D CPU): binarisation, contours, holes, triangulation, buffers.
2. Implementer the phase 3F (renderer GPU): GL-thread strict, upload, draw pipeline, interactions viewer.
3. Brancher the actions metier GUI:
 - Files tab: upload/delete/print/download.
 - Dialogs Upload/Print: payloads and appels API reels.
4. Completer the phase 3G:
 - invalidation cache 3D reelle,
 - instrumentation perf CPU/GPU branchee to the pipeline.
5. Completer the strategie tests:
 - goldens (`cube/cube2/misteer`),
 - e2e UI minimal,
 - tests 3D determinisme + no-rebuild.

---

## Resume court

- Base cloud, auth/session, hardening logs and decode PWMB are en place.
- The gap principal remaining is the pipeline 3D complet (CPU+GPU) and the branchement metier final of boutons UI.
