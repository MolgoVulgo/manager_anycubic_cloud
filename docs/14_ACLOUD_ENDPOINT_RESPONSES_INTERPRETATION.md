### But
Décrire le **retour des endpoints** Anycubic Cloud et la manière de les **interpréter** côté client.

### Entrées
- Réponse HTTP (`status`, body JSON, headers).
- Endpoint appelé (auth, files, upload, printers, print, etc.).

### Sorties attendues
- Décision déterministe : succès, retry, refresh/relogin, ou erreur fonctionnelle.
- Données extraites dans un format exploitable (quota, files, printers, URLs signées, IDs).


### Notation des chemins
Sauf mention contraire, les chemins d’endpoint dans ce document sont **complets** (préfixe inclus) :

- Base : `https://cloud-universe.anycubic.com`
- Préfixe : `/p/p/workbench/api`

Exemple : `GET /p/p/workbench/api/v3/public/getoauthToken`

### Règles globales d’interprétation (contrats)
1. **Statut HTTP**
- Succès attendu: `200`/`201` (et parfois `202` pour actions async comme delete/print).
- `429` ou `5xx`: erreurs transitoires -> retry borné + backoff.
- `401/403`: session invalide/expirée -> refresh token ou relogin.
- Autres statuts hors contrat -> erreur API.

2. **Payload JSON**
- Si body JSON est un objet: utiliser tel quel.
- Si body JSON est une liste: encapsuler logiquement en `data`.
- Si JSON invalide: erreur API (réponse non exploitable).

3. **Code applicatif Anycubic**
- Si champ `code` absent: ne pas bloquer, continuer.
- Si `code == 1`: succès métier.
- Si `code != 1`: échec métier, utiliser `msg`/`message`/`error`.

4. **Extraction des données utiles**
- Si `data` est un objet: `data` devient la source principale.
- Sinon: utiliser le payload racine.
- Pour listes: chercher `items`, `files`, `printers`, `list`, `results`, `rows`, sinon `data` si liste.

### Interprétation par endpoint
1. **`GET /p/p/workbench/api/v3/public/getoauthToken`**
- Attendu: `code=1`, `data.id_token` (ou token équivalent).
- Interprétation: token OAuth intermédiaire pour login applicatif.
- Échec: relancer flux OAuth (code expiré/invalide).

2. **`POST /p/p/workbench/api/v3/public/loginWithAccessToken`**
- Attendu: `code=1`, `data.login_status`, `data.token` et/ou token d’accès.
- Interprétation: session applicative établie.
- Si token manquant: session non utilisable.

3. **`POST /p/p/workbench/api/work/index/getUserStore`**
- Attendu: `code=1`, métriques quota (`used`, `total`, `used_bytes`, `total_bytes`).
- Interprétation: endpoint de validation de session + quota.
- Si réponse OK sans quota complet: considérer session valide, quota partiel.

4. **`POST /p/p/workbench/api/work/index/files`** et **`/work/index/userFiles`**
- Attendu: liste de fichiers dans un des champs supportés (`files`, `list`, `items`, etc.).
- Interprétation: mapper chaque item vers `{id, name, size, status, timestamps}`.
- Si première route échoue: fallback sur la route alternative.

5. **`GET /p/p/workbench/api/api/work/gcode/info?id=...`**
- Attendu: objet gcode (layers, durée, résine, extra).
- Interprétation: infos techniques du fichier/print profile.
- Si champs absents: garder `extra` brut pour compatibilité.

6. **`POST /p/p/workbench/api/work/index/getDowdLoadUrl`**
- Attendu: URL signée dans `data.url` (ou équivalent), ou directement `data` sous forme de string URL.
- Requête recommandée: envoyer `id` numérique quand `file_id` est numérique (comportement le plus compatible observé), puis fallback sur variantes de champs (`file_id`, `fileId`, `ids`) si besoin.
- Interprétation: effectuer un `GET` direct sur URL signée, sans headers d'auth cloud (`Authorization`, `XX-*`).
- Si URL absente: erreur métier (download impossible).

7. **Upload: `lockStorageSpace` -> `PUT preSignUrl` -> `newUploadFile` -> `unlockStorageSpace`**
- `lockStorageSpace`: doit fournir `preSignUrl` + `id` lock.
- `PUT preSignUrl`: succès binaire (`200/201`) sans headers d'auth cloud (`Authorization`, `XX-*`).
- `newUploadFile`: attendu `data.id` (file_id enregistré).
- `unlockStorageSpace`: appeler même en erreur partielle (best effort).
- Interprétation: upload réussi uniquement si `PUT` + `register` valides.

8. **`POST /p/p/workbench/api/work/index/delFiles`**
- Attendu: `200/201/202` + `code=1`.
- Interprétation: suppression acceptée (immédiate ou asynchrone).

9. **`POST /work/operation/sendOrder`**
- Attendu: `200/201/202` + payload de confirmation éventuel.
- Interprétation: ordre d’impression soumis, suivi via endpoints projet/printer.

10. **`GET /work/printer/getPrinters`**
- Attendu: liste imprimantes.
- Interprétation: mapping `online` tolérant (`1/true/yes/online/connected`).

### Modèles JSON reçus (exemples)
1. **OAuth token exchange (`getoauthToken`)**
```json
{
  "code": 1,
  "data": {
    "id_token": "<jwt>"
  }
}
```

2. **Login with access token (`loginWithAccessToken`)**
```json
{
  "code": 1,
  "data": {
    "login_status": 1,
    "token": "<session_token>",
    "user": {
      "id": 12345,
      "email": "user@example.com"
    }
  }
}
```

3. **Quota (`getUserStore`)**
```json
{
  "code": 1,
  "data": {
    "used_bytes": 123456789,
    "total_bytes": 2147483648,
    "used": "117.7 MB",
    "total": "2.0 GB"
  }
}
```

4. **Liste fichiers (`files` ou `userFiles`)**
```json
{
  "code": 1,
  "data": [
    {
      "id": 30553490,
      "old_filename": "model.pwmb",
      "filename": "...pwmb",
      "size": 44851383,
      "status": 1,
      "gcode_id": 44306216,
      "url": "https://cdn.cloud-universe.anycubic.com/file/...",
      "thumbnail": "https://...jpg",
      "region": "us-east-2",
      "bucket": "workbentch",
      "path": "file/.../model.pwmb"
    }
  ]
}
```

5. **Détails gcode (`gcode/info`)**
```json
{
  "code": 1,
  "data": {
    "layers": 287,
    "estimate": 3114,
    "layer_height": 0.05,
    "supplies_usage": 44.19,
    "machine_name": "Anycubic Photon M3 Plus"
  }
}
```

6. **Download URL (`getDowdLoadUrl`)**
```json
{
  "code": 1,
  "data": "https://workbentch.s3.us-east-2.amazonaws.com/...&X-Amz-Signature=..."
}
```

7. **Upload lock (`lockStorageSpace`)**
```json
{
  "code": 1,
  "data": {
    "id": 24999108,
    "preSignUrl": "https://workbentch.s3.us-east-2.amazonaws.com/..."
  }
}
```

8. **Upload register (`newUploadFile`)**
```json
{
  "code": 1,
  "data": {
    "id": 30553490
  }
}
```

9. **Upload status (`getUploadStatus`)**
```json
{
  "code": 1,
  "data": {
    "status": 1,
    "gcode_id": 44306216
  }
}
```

10. **Suppression (`delFiles`) / unlock (`unlockStorageSpace`)**
```json
{
  "code": 1,
  "data": ""
}
```

11. **Exemple d’erreur métier**
```json
{
  "code": 0,
  "msg": "invalid token",
  "data": null
}
```

### Gestion des erreurs métier
- Priorité message: `msg` -> `message` -> `error` -> message générique.
- Toujours journaliser endpoint + request_id + status + code applicatif (sans secrets).
- Ne jamais journaliser tokens complets, cookies, URLs signées complètes.

### Matrice de décision rapide
1. HTTP `2xx` + (`code` absent ou `code=1`) -> succès.
2. HTTP `2xx` + `code!=1` -> erreur métier (pas de retry aveugle).
3. HTTP `401/403` -> refresh/relogin.
4. HTTP `429/5xx` -> retry borné.
5. JSON invalide/inattendu -> erreur API.

### Objectif
Avoir une interprétation homogène des réponses endpoints pour éviter les régressions, sécuriser les flux auth/upload/print et simplifier le diagnostic.

---
