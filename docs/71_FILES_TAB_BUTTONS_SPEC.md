### But
Documenter de facon exhaustive tous les boutons lies a l'onglet `Files` et leur comportement reel (UI, callbacks, flux cloud, erreurs).

### Perimetre
- UI onglet `Files`: `app_gui_qt/tabs/files_tab.py`.
- Wiring callbacks: `app_gui_qt/app.py`.
- Flux cloud appeles par ces callbacks: `accloud_core/api.py` + `accloud_core/endpoints.py`.
- Clarification: les boutons du header global (`Upload Dialog`, `Print Dialog`, `3D Viewer Dialog`) ne font pas partie de l'onglet `Files`.

### Entrees
- Session cloud active (ou cache local disponible).
- `build_files_tab(...)` avec callbacks potentiels:
  - `on_refresh`
  - `on_upload`
  - `on_download`
  - `on_delete`
  - `on_list_printers`
  - `on_print`
  - `on_open_viewer`
- Liste `FileItem` issue du refresh.

### Sorties attendues
- Comprendre pour chaque bouton:
  - etat (actif, stub, conditionnel),
  - action exacte,
  - messages utilises,
  - effets UI,
  - endpoints cloud impliques (si applicable).

### Etat general de l'onglet
1. **Nature de l'onglet**
- Onglet fonctionnel cote UI.
- Actions reellement branchees: `Refresh`, `Upload .pwmb`, `Delete`, `Details`, `Print`, `Download`.
- Action conditionnelle: `Open 3D Viewer` (visible uniquement pour les fichiers `.pwmb`).

2. **Chargement initial (hors clic utilisateur)**
- Au demarrage, l'app tente d'afficher un snapshot cache puis lance une synchro cloud asynchrone.
- Pendant cette phase, le bouton `Refresh` est desactive via `set_loading(True, "Loading cloud data...")`.

### Matrice rapide des boutons de l'onglet `Files`
| Bouton | Emplacement | Etat actuel | Appel cloud direct | Notes |
|---|---|---|---|---|
| `Refresh` | Toolbar onglet | Actif | Oui (via callback) | Desactive pendant chargement |
| `Upload .pwmb` | Toolbar onglet | Actif | Oui (via callback) | 1 upload simultane max, refresh auto apres succes |
| `Delete` | Carte fichier (haut droite) | Actif | Oui (via callback) | Confirmation + suppression + refresh |
| `Details` | Carte fichier (actions) | Actif | Non (local) | Ouvre `File Details` read-only |
| `Print` | Carte fichier (actions) | Actif | Oui (via callbacks) | Selection imprimante + `sendOrder` |
| `Download` | Carte fichier (actions) | Actif | Oui (via callback) | 1 download simultane max |
| `Open 3D Viewer` | Carte fichier (actions) | Actif conditionnel | Non cloud | Affiche seulement pour `.pwmb` |

### Boutons de la toolbar (haut de l'onglet)
1. **`Refresh`**
- Emplacement: toolbar de l'onglet.
- Etat: **actif** si callback `on_refresh` fourni.
- Si `on_refresh` absent:
  - statut: `No cloud refresh callback configured.`
  - aucun thread lance.
- Garde-fou:
  - si un refresh est deja en cours (`files-refresh` vivant), le clic est ignore.
- Action UI:
  - `set_loading(True, "Loading cloud data...")`.
  - bouton desactive pendant le chargement.
  - thread asynchrone + polling timer (70 ms).
- Flux callback par defaut dans `app.py`:
  - `api.get_quota()` -> endpoint `POST /p/p/workbench/api/work/index/getUserStore`.
  - `api.list_files(page=1, page_size=20)` -> endpoint principal `POST /p/p/workbench/api/work/index/files`, fallback `POST /p/p/workbench/api/work/index/userFiles`.
  - enrichissement metadata manquantes via `api.get_gcode_info(...)` (parallelise, max 4 workers).
  - sauvegarde snapshot local quand quota ou fichiers sont presents.
  - fallback cache local si cloud indisponible ou echec partiel.
- Messages statut observes:
  - succes avec donnees: `Loaded N files from cloud API.`
  - succes sans fichier: `No file returned by cloud API.`
  - echec thread: `Refresh failed: ...`
  - echec partiel callback: `Refresh partial failure: ...`
  - fallback cache: `Cloud unavailable, loaded from local cache.`

2. **`Upload .pwmb`**
- Emplacement: toolbar de l'onglet.
- Etat: **actif**.
- Pre-conditions et garde-fous:
  - si `on_upload` absent: popup `No cloud upload callback configured.`.
  - si un upload est deja en cours (`files-upload` vivant): popup `A file upload is already running.`.
  - si un refresh est deja en cours (`files-refresh` vivant): popup `Refresh in progress`.
- Flux UI:
  - ouverture d'un `QFileDialog.getOpenFileName(...)`:
    - titre: `Select .pwmb file`
    - filtre: `PWMB files (*.pwmb);;All files (*)`
  - validation locale:
    - le chemin doit etre un vrai fichier,
    - extension requise: `.pwmb`.
  - statut: `Uploading <file_name>...`.
  - worker asynchrone + polling timer (80 ms).
- Succes:
  - popup `Upload complete`,
  - statut: `Uploaded <file_name> (id=<file_id>). Refreshing list...` (ou variante sans id),
  - refresh automatique de la liste (`refresh()`).
- Echec:
  - popup `Upload failed`,
  - statut: `Upload failed for <file_name>: <exception>`.
- Flux cloud (callback par defaut de l'app):
  1. appel `api.upload_file(source_path)`,
  2. lock cloud storage (`lockStorageSpace`),
  3. upload binaire `PUT` vers URL pre-signée, sans headers d'auth cloud (`Authorization`, `XX-*`),
  4. enregistrement (`newUploadFile`),
  5. unlock storage (`unlockStorageSpace`).

### Boutons des cartes fichier
1. **`Delete`**
- Emplacement: coin haut droit de la carte.
- Etat: **actif**.
- Pre-conditions et garde-fous:
  - si `on_delete` absent: popup `No cloud delete callback configured.`.
  - si une suppression est deja en cours (`files-delete` vivant): popup `A file deletion is already running.`.
- Flux UI:
  - popup de confirmation `Delete file?` (Yes/No, defaut No).
  - si confirmation: statut `Deleting <file_name>...`.
  - worker asynchrone + polling timer (80 ms).
- Succes:
  - popup `Delete complete`.
  - statut `Deleted <file_name>. Refreshing list...`.
  - refresh automatique via `refresh()` si callback `on_refresh` disponible.
- Echec:
  - popup `Delete failed`.
  - statut `Delete failed for <file_name>: <exception>`.
- Flux cloud (callback par defaut de l'app):
  1. validation locale `file_id`.
  2. appel `api.delete_file(file_id)`.
  3. endpoint cloud: `POST /p/p/workbench/api/work/index/delFiles`.
  4. payload tente en priorite `idArr=[<id numerique>]` quand possible, avec fallback string.
  5. succes metier exige `code == 1` (sinon message cloud remonte en erreur).

2. **`Details`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.
- Action:
  - ouvre un dialog `File Details`.
  - contenu read-only (`QPlainTextEdit`) avec sections:
    - `[General]`
    - `[Slicing]`
    - `[Cloud]`
  - inclut metadonnees techniques (id, gcode id, statut, dimensions, temps, printer names, md5, urls, bucket, region, etc.).
- Bouton secondaire dans ce flux:
  - `Close` (via `QDialogButtonBox.StandardButton.Close`) ferme le dialog.

3. **`Print`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.
- Pre-conditions et garde-fous:
  - si `on_print` absent: popup `No cloud print callback configured.`.
  - si `on_list_printers` absent: popup `No cloud printer list callback configured.`.
  - si chargement imprimantes deja en cours: popup `Printer list is already loading.`.
  - si envoi print deja en cours: popup `A print request is already running.`.
- Flux UI:
  - au clic: statut `Loading printers for <file_name>...`.
  - worker asynchrone qui appelle `on_list_printers()`.
  - popup de selection (`QInputDialog`) avec la liste des imprimantes:
    - priorite aux imprimantes online (`online=True`),
    - fallback sur toutes les imprimantes si aucune online.
  - si annulation de la selection: statut `Print cancelled.`.
  - si confirmation: statut `Sending print order for <file_name> to <printer_name>...`.
  - worker asynchrone d'envoi print (`on_print(file_item, printer)`).
- Succes:
  - statut `Print order sent for <file_name> on <printer_name>.`
  - popup `Print order sent`.
  - refresh du statut imprimante declenche immediatement apres succes (onglet `Printer`), puis second refresh differe (~3.5s) pour capter la propagation cloud.
- Echec:
  - chargement imprimantes: popup `Print failed` + message `Could not load printers: ...`
  - envoi ordre: popup `Print failed` + message `Print failed for <file_name> on <printer_name>: ...`
- Flux cloud (wiring standard dans `app.py`):
  1. `on_list_printers` reutilise le callback de refresh imprimantes (`api.list_printers()` + fallback cache local).
  2. `on_print` valide `file_id` et `printer_id`.
  3. appel `api.send_print_order(file_id, printer_id)` avec priorite au payload legacy observe comme le plus compatible:
     - form-data: `printer_id`, `project_id=0`, `order_id=1`, `is_delete_file=0`,
     - champ `data` JSON stringifie: `{"file_id":"...","matrix":"","filetype":0,"project_type":1,"template_id":-2074360784}`.
  4. fallback automatique vers payload JSON (legacy puis minimal) si rejet du payload precedent.
  5. validation du code metier Anycubic (`code == 1`), sinon remontée du message cloud (`msg`/`message`) vers popup `Print failed`.
  6. endpoint cloud: `POST /p/p/workbench/api/work/operation/sendOrder`.

4. **`Download`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.

- Pre-conditions et garde-fous:
  - si `on_download` absent: popup `No cloud download callback configured.`.
  - si un download est deja en cours (`files-download` vivant): popup `A file download is already running.`.
  - un seul download simultane est autorise.

- Flux UI:
  - ouverture d'un `QFileDialog.getSaveFileName(...)`:
    - titre: `Save cloud file`
    - chemin par defaut: `~/Downloads/<nom_suggere>`
    - filtre: `PWMB files (*.pwmb);;All files (*)`
  - si annulation du dialog: sortie sans action.
  - si fichier cible existant: confirmation `Overwrite existing file?` (Yes/No, defaut No).
  - creation du dossier parent (`mkdir(parents=True, exist_ok=True)`) avant lancement.
  - statut: `Downloading <file_name>...`.
  - worker asynchrone + polling timer (80 ms).

- Succes:
  - statut: `Downloaded <file_name>.`
  - popup `Download complete` avec chemin final.

- Echec:
  - statut: `Download failed for <file_name>: <exception>`
  - popup `Download failed`.

- Nom de fichier suggere:
  - base = nom fichier (sanitise).
  - fallback = `file_id` puis `cloud-file`.
  - extension completee depuis `file_extension` si necessaire.

- Flux cloud (callback par defaut de l'app):
  1. Validation locale `file_id` (sinon `ValueError`).
  2. Appel `POST /p/p/workbench/api/work/index/getDowdLoadUrl` (priorite `id` numerique si possible, puis variantes `id`, `file_id`, `fileId`, `ids`).
  3. Extraction URL signee (`url`/`download_url`/`signedUrl`/`signed_url`) avec fallback si `data` est directement une string URL.
  4. `GET` direct sur URL signee **sans** headers d'auth cloud (`Authorization`, `XX-*`) pour eviter les erreurs S3 (`400`).
  5. Ecriture binaire locale vers la destination.

5. **`Open 3D Viewer`**
- Emplacement: rangee d'actions de la carte.
- Visibilite:
  - bouton rendu uniquement si `file_item.name.lower().endswith(".pwmb")`.
- Etat:
  - **actif conditionnel** si callback `on_open_viewer` fourni.
  - sinon **stub UI** (`Design only`).
- Comportement du wiring actuel (`app.py`):
  - callback injecte: `lambda: _open_viewer_dialog(window)` (sans argument fichier).
  - `FilesTab` tente d'abord `on_open_viewer(file_item)`.
  - un `TypeError` est attendu puis fallback `on_open_viewer()`.
  - resultat: ouverture du dialog viewer global, sans chargement explicite du fichier clique.

### Boutons secondaires declenches depuis l'onglet `Files`
1. **Dialog overwrite (`Download`)**
- Boutons: `Yes` / `No`.
- Effet:
  - `Yes`: ecrase le fichier cible.
  - `No`: annule le download.

2. **Popups information/warning**
- Bouton natif `OK` (ou equivalent selon plateforme) pour fermer:
  - popup `Upload complete`,
  - popup `Upload failed`,
  - popup `Upload in progress`,
  - popup `Download complete`,
  - popup `Download failed`,
  - popup `Download in progress`.

3. **Dialog `File Details`**
- Bouton: `Close`.
- Effet: ferme la fenetre de details.

### Comportements lies (non-boutons, mais impacts visibles)
1. **Miniatures**
- Chargement asynchrone en fond (`httpx.get`, semaphore 4 workers).
- Cache disque optionnel via `CacheStore` + TTL.
- En cas d'echec: placeholder texte (`EXT` + `100x100`).

2. **Resume quota**
- Recalcule a chaque `render_files(...)`/`set_quota(...)`.
- Format: `used / total (%), free, nombre de fichiers`.

3. **Liste fichiers limitee a la page 1**
- Le callback standard appelle `list_files(page=1, page_size=20)`.
- Donc l'onglet affiche actuellement au plus 20 fichiers par refresh (pas de pagination UI).

### Contrats d'usage recommandes
1. Garder `Refresh` comme point d'entree unique de synchro cloud (avec fallback cache deja en place).
2. Ajouter une suppression multiple (batch) si besoin operationnel, en reutilisant `api.delete_file(...)`/`idArr`.
3. Etendre le flux `Print` si besoin (confirmation supplementaire, options avancees cloud, file d'attente multi-demandes).
4. Faire evoluer `Open 3D Viewer` pour transmettre et charger le fichier clique (pas seulement ouvrir le dialog global).

### Objectif
Fournir une reference precise pour distinguer:
- les boutons operationnels en production UI,
- les boutons encore en stub,
- les flux cloud effectivement appeles aujourd'hui depuis l'onglet `Files`.

---
