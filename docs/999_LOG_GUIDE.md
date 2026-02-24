# 999 — LOG GUIDE (contrat de logs)

Objectif : définir un **contrat stable** pour les logs (qui / quoi / comment / où), afin que :

* les tests puissent empêcher les régressions (fuite de secrets, formats cassés),
* Codex génère du code **déterministe** (pas de “logging inventé”),
* le support (toi) puisse diagnostiquer sans ouvrir un IDE.

Ce document est **normatif** : si le code contredit ce guide, le code est considéré en défaut.

---

## 0) Principes

1. **Deux fichiers minimum** (contrat de logs) :

* **App (persistant, JSONL)** : `accloud_app.log` → **tous les logs applicatifs**, **sans** logs HTTP.
* **HTTP (persistant, JSONL)** : `accloud_http.log` → **uniquement** les échanges transport avec le cloud.

2. **Un seul événement = une ligne** (pas de multi-lignes), pour permettre `tail -f` et le parsing.

3. **Horodatage canonique** : ISO-8601 avec timezone (ex: `2026-02-23T22:15:01+01:00`).

4. **Redaction obligatoire** : aucun secret ne doit transiter vers un sink de logs.

5. **Corrélation obligatoire** : toute opération utilisateur (clic UI, import, build 3D, upload) doit porter un `op_id` unique propagé.

---

## 1) Où sont écrits les logs

### 1.1 Chemins

* **Répertoire logs** : `./.accloud/logs/`
* Override : `ACCLOUD_LOG_DIR=/chemin`

### 1.2 Fichiers

* **App (persistant, JSONL)** : `{LOG_DIR}/accloud_app.log`

* **App (rotations)** : `{LOG_DIR}/accloud_app.log.1`, `.2`, etc.

* **HTTP (persistant, JSONL)** : `{LOG_DIR}/accloud_http.log`

* **HTTP (rotations)** : `{LOG_DIR}/accloud_http.log.1`, `.2`, etc.

* **Render 3D (persistant, JSONL)** : `{LOG_DIR}/accloud_render3d.log`

* **Render 3D (rotations)** : `{LOG_DIR}/accloud_render3d.log.1`, `.2`, etc.

Règle de séparation :

* `accloud_http.log` : événements `event` préfixés `http.` et `component=accloud.http` **uniquement**.
* `accloud_app.log` : **tout le reste** (UI, orchestration, session/auth, API métier, PWMB, 3D/GPU), **sans** événements `http.*`.
* `accloud_render3d.log` : sous-ensemble dédié rendu 3D (composants `render3d.*`, `pwmb.*`, erreurs/événements viewer 3D).

### 1.3 Rotation / rétention

* Handler : rotation **par taille**
* Defaults :

  * `ACCLOUD_LOG_MAX_BYTES=10485760` (10 MiB)
  * `ACCLOUD_LOG_BACKUPS=5` (**conserver 5 versions** pour `accloud_app.log` et 5 pour `accloud_http.log`)

### 1.4 Compression des rotations (obligatoire)

* Règle : le fichier **courant** reste en clair (`*.log`).
* Tous les backups (`*.log.1`, `*.log.2`, …) sont **compressés** en `gzip` dès la rotation.

Nommage attendu :

* `accloud_app.log.1.gz`, `accloud_app.log.2.gz`, …
* `accloud_http.log.1.gz`, `accloud_http.log.2.gz`, …
* `accloud_render3d.log.1.gz`, `accloud_render3d.log.2.gz`, …

Config :

* `ACCLOUD_LOG_COMPRESS=1` (on/off)
* `ACCLOUD_LOG_COMPRESS_LEVEL=6` (1..9)

Règles :

* `ACCLOUD_LOG_BACKUPS` compte le **nombre de backups compressés** conservés.
* La compression ne doit pas bloquer le thread UI : compression hors thread UI.

Note UI : l’onglet LOG tail **uniquement** les fichiers actifs (`*.log`). Les archives `*.gz` sont hors flux temps réel.

---

## 2) Niveaux (severity)

Niveaux autorisés : `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

* `DEBUG` : détails volumineux (désactivé par défaut).
* `INFO` : événements normaux (par défaut).
* `WARNING` : comportement inattendu mais récupérable (retry, fallback).
* `ERROR` : opération échoue (mais app continue).
* `CRITICAL` : état incohérent / corruption / crash imminent.

Config :

* `ACCLOUD_LOG_LEVEL=INFO`
* `ACCLOUD_HTTP_LOG_LEVEL=INFO`

---

## 3) Corrélation : `op_id`, `req_id`, propagation

### 3.1 `op_id` (obligatoire)

* Créé au démarrage de chaque action “haute” :

  * import HAR, login, refresh session
  * liste fichiers, upload, delete
  * open PWMB, build contours, build GPU buffers, render
* Format : UUID4 ou équivalent (`8-4-4-4-12`), string.

### 3.2 `req_id` (HTTP)

* Un identifiant par requête HTTP (UUID4 court ou compteur monotone).
* Toujours logué pour `http.request` + `http.response` et identique entre les deux.

### 3.3 Propagation

* Tout ce qui est asynchrone / thread pool doit recevoir `op_id` en paramètre explicite (pas de variable globale implicite).

---

## 4) Redaction (anti-fuite)

### 4.1 Ce qui doit être **toujours** redigé

Clés/headers contenant (case-insensitive) :

* `token`, `authorization`, `cookie`, `set-cookie`, `secret`,
* `signature`, `nonce`, `timestamp`,
* `password`, `email`, `phone`, `user_id`, `refresh`.

Valeur remplacée par : `"[REDACTED]"`.

### 4.2 URLs signées / query-string

* Ne jamais loguer une URL signée complète avec query sensible.
* Loguer :

  * `url.base` (scheme + host + path)
  * `url.query_keys` (liste des clés)
  * éventuellement `url.query_hash` (sha256 du query string brut) **sans** les valeurs.

### 4.3 JSON payloads

* Les payloads requête/réponse peuvent être logués **uniquement** après redaction recursive :

  * profondeur max configurable (default 6),
  * taille max (default 64 KiB) avec truncation (`"...TRUNCATED"`).

### 4.4 Tests obligatoires

* Un test doit échouer si un log contient une sous-chaîne de type token/cookie :

  * `Bearer `
  * `XX-Token`
  * `Set-Cookie:`
  * patterns JWT (regex `eyJ[A-Za-z0-9_-]+\.`)
* Un test doit valider que les champs requis existent (schéma JSONL).

---

## 5) Format JSONL (canon)

Chaque ligne du fichier `accloud_http.log` est un JSON objet.

### 5.1 Champs requis (toutes lignes)

* `ts` : string ISO-8601 tz
* `level` : string
* `component` : string (voir §6)
* `event` : string (voir §7)
* `msg` : string (courte, humaine)
* `op_id` : string
* `pid` : int
* `thread` : string (nom) ou int (id)

### 5.2 Champs optionnels standard

* `req_id` : string (si contexte HTTP)
* `duration_ms` : number
* `error` : objet

  * `type`, `message`, `stack` (stack optionnel, max 8 KiB, mono-ligne ou array)
* `tags` : array[string]
* `data` : objet libre (mais redigé + borné)

### 5.3 Sous-objets recommandés

#### `http`

* `method` : string
* `url_base` : string
* `query_keys` : array[string]
* `status` : int (response)
* `attempt` : int (retry count, 1..n)
* `timeout_s` : number
* `bytes_out` : int
* `bytes_in` : int

#### `accloud`

* `endpoint` : string (nom stable : `files.list`, `storage.lock`, etc.)
* `code` : int (code métier Anycubic si dispo)
* `msg_api` : string (message API redigé si besoin)

#### `pwmb`

* `pwmb_path_hash` : string (sha256 du chemin, pas le chemin brut si sensible)
* `layer_index` : int
* `W` / `H` : int
* `aa` : int
* `decoder` : string (`pw0`, `pws:auto`, etc.)

#### `render3d`

* `stage` : string (`decode`, `mask`, `loops`, `triangulate`, `upload`, `draw`)
* `layers_visible` : int
* `tris` : int, `verts` : int (si dispo)

---

## 6) “Qui logue” : composants autorisés

Valeurs `component` (stables) :

### Anycubic Cloud

* `accloud.http` : transport (httpx), retry/backoff, status, timings
* `accloud.auth` : import HAR, normalisation tokens (sans valeurs)
* `accloud.session` : lecture/écriture session.json (sans tokens)
* `accloud.api` : mapping endpoints → modèles

### PWMB

* `pwmb.parse` : container, tables, offsets
* `pwmb.decode` : décodage pw0/pws, stats par couche
* `pwmb.contours` : mask→edges→loops, simplification, holes

### 3D / GPU

* `render3d.build` : geometry buffers, triangulation, cache
* `render3d.gpu` : upload buffers, draw pipeline, erreurs GL

### App / UI

* `app.gui` : actions utilisateur, état UI, annulation
* `app.task` : orchestration threads/pool, progression

---

## 7) “Quoi loguer” : catalogue minimal d’événements

Le champ `event` est **stable** (API interne).
Le texte humain est dans `msg`.

### 7.1 HTTP

* `http.request` (INFO/DEBUG)
* `http.response` (INFO)
* `http.retry` (WARNING)
* `http.error` (ERROR)

### 7.2 Session / Auth

* `session.load_ok` (INFO)
* `session.load_fail` (ERROR)
* `session.save_ok` (INFO)
* `auth.har_import_ok` (INFO)
* `auth.har_import_fail` (ERROR)

### 7.3 Anycubic API

* `api.call_ok` (INFO) : `code==1`
* `api.call_fail` (WARNING/ERROR) : `code!=1` ou JSON invalide

### 7.4 PWMB

* `pwmb.open_ok` (INFO)
* `pwmb.open_fail` (ERROR)
* `pwmb.decode_layer_ok` (INFO/DEBUG)
* `pwmb.decode_layer_fail` (ERROR)
* `pwmb.contours_ok` (INFO/DEBUG)
* `pwmb.contours_fail` (ERROR)

### 7.5 Build / Render 3D

* `build.stage_start` (INFO/DEBUG)
* `build.stage_done` (INFO)
* `build.stage_fail` (ERROR)
* `gpu.upload_ok` (INFO)
* `gpu.upload_fail` (ERROR)
* `gpu.draw_ok` (DEBUG/INFO)
* `gpu.draw_fail` (ERROR)

### 7.6 UI

* `ui.action` (INFO) : clic / commande
* `ui.error` (ERROR)
* `ui.cancel` (WARNING)

---

## 8) Règles spécifiques au fichier HTTP (`accloud_http.log`)

### 8.1 Contenu autorisé

* Toujours : method, url_base, status, timings, endpoint name, code métier.
* Optionnel : payloads JSON **redigés + tronqués** (voir §4.3).

### 8.2 Granularité

* Une paire `http.request` / `http.response` par requête.
* Si retry : un `http.retry` par tentative, et `attempt` incrémenté.

### 8.3 Ce qui est interdit

* Headers bruts complets.
* Cookies / Set-Cookie.
* Tokens, signatures, nonce, timestamp.
* URL signée avec valeurs de query.

### 8.4 Règle d’exclusivité

* `accloud_http.log` ne contient **que** des événements `http.*` (transport).
* Toute info applicative (UI, session, parsing, rendu, erreurs métier) va dans `accloud_app.log`.

---

## 9) Contrat UI : onglet LOG (Qt)

### 9.1 Sources

* Tail de `{LOG_DIR}/accloud_app.log` (poll 1s).
* Tail de `{LOG_DIR}/accloud_http.log` (poll 1s).

### 9.2 Comportement

* Lire en append ; gérer :

  * rotation (fichier remplacé)
  * truncate (taille réduite)
* Parser JSON par ligne ; si ligne invalide :

  * afficher comme “raw” avec tag `parse_error` (mais ne pas crasher).

### 9.3 Colonnes minimales

* `ts`, `level`, `component`, `event`, `msg`, `op_id`, `req_id`, `duration_ms`, `http.status`

### 9.4 Filtres

* Niveau (>=)
* component
* event
* op_id (exact)
* recherche texte (msg)
* source (`app` / `http`)

---

## 10) Checklist d’acceptation (tests + revue)

1. Tous les events listés (§7) existent au moins une fois dans des tests (smoke).
2. Aucun secret ne passe (tests regex §4.4).
3. JSONL : chaque ligne parse en JSON et contient les champs requis (§5.1).
4. `op_id` présent sur 100% des lignes.
5. Rotation : écrire > MAX_BYTES ne casse pas le tail UI (test integration).
