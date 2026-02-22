### But
Fournir un catalogue des endpoints Anycubic Cloud, sur le même modèle documentaire, pour implémentation et maintenance.

### Périmètre
- Endpoints **observés** dans HAR/logs/docs/code du projet.
- Regroupement par domaine fonctionnel.
- Méthodes + chemins + URL complète quand utile.

### Hosts / bases à utiliser
- `https://cloud-universe.anycubic.com` (API Web workbench)
- `https://uc.makeronline.com` (OAuth / compte)
- `https://api.makeronline.com` (services makeronline observés)
- `https://cdn.cloud-universe.anycubic.com` (assets/CDN)

### Authentification / session
1. OAuth authorize
- `GET https://uc.makeronline.com/login/oauth/authorize`

2. OAuth logout
- `GET https://uc.makeronline.com/api/logout`

3. Exchange code -> token
- `GET /p/p/workbench/api/v3/public/getoauthToken`
- URL : `https://cloud-universe.anycubic.com/p/p/workbench/api/v3/public/getoauthToken?code=<oauth_code>`

4. Login applicatif avec access token
- `POST /p/p/workbench/api/v3/public/loginWithAccessToken`
- URL : `https://cloud-universe.anycubic.com/p/p/workbench/api/v3/public/loginWithAccessToken`

5. Login mobile (vu dans traces APK)
- `POST api/user/public/login`

### Quota / capacité
1. Store quota
- `POST /p/p/workbench/api/work/index/getUserStore`

### Fichiers cloud
1. Listing fichiers (variante A)
- `POST /p/p/workbench/api/work/index/files`

2. Listing fichiers (variante B observée logs)
- `POST /p/p/workbench/api/work/index/userFiles`

3. URL de téléchargement signée
- `POST /p/p/workbench/api/work/index/getDowdLoadUrl`

4. Suppression
- `POST /p/p/workbench/api/work/index/delFiles`

5. Renommage
- `POST /p/p/workbench/api/work/index/renameFile`

6. Statut upload
- `POST /p/p/workbench/api/work/index/getUploadStatus`

### GCode / informations modèle
1. Détails gcode
- `GET /p/p/workbench/api/api/work/gcode/info?id=<gcode_id>`

### Upload (workflow multi-étapes)
1. Lock espace stockage
- `POST /p/p/workbench/api/v2/cloud_storage/lockStorageSpace`

2. Upload binaire direct
- `PUT <preSignUrl>` (URL signée renvoyée par lockStorageSpace)

3. Enregistrement du fichier uploadé
- `POST /p/p/workbench/api/v2/profile/newUploadFile`

4. Unlock espace stockage
- `POST /p/p/workbench/api/v2/cloud_storage/unlockStorageSpace`

### Imprimantes
1. Liste imprimantes
- `GET /p/p/workbench/api/work/printer/getPrinters`

2. Info imprimante (endpoint historique)
- `POST /p/p/workbench/api/work/printer/Info`

3. Info imprimante v2
- `GET /p/p/workbench/api/v2/printer/info?id=<printer_id>`

4. Options imprimante (vu APK)
- `POST api/v2/device/getPrinterOptions`

5. Config fonctions device (vu APK)
- `POST api/v2/device_function/funConfig`

### Projets / jobs d’impression
1. Liste projets
- `GET /p/p/workbench/api/work/project/getProjects`

2. Détail projet
- `GET /p/p/workbench/api/v2/project/info?id=<project_id>`

3. Rapport projet/tâche
- `GET /p/p/workbench/api/work/project/report?id=<task_id>`

4. Historique impression
- `GET /p/p/workbench/api/v2/project/printHistory?limit=<n>&page=<n>&printer_id=<printer_id>`

### Impression
1. Envoi commande impression
- `POST /p/p/workbench/api/work/operation/sendOrder`

### Messages / notifications
1. Compteur messages
- `GET /p/p/workbench/api/v2/message/getMessageCount`

2. Liste messages
- `POST /p/p/workbench/api/v2/message/getMessages`

### Endpoints annexes observés
1. Download service makeronline
- `https://api.makeronline.com/file/fileService/download`

2. Assets application
- `https://cdn.cloud-universe.anycubic.com/application/android.png`
- `https://cdn.cloud-universe.anycubic.com/application/ios.png`

3. Environnement
- `https://workbentch.s3.us-east-2.amazonaws.com/workshop/environment.ini`

### Contrats d’usage recommandés
1. Prioriser les endpoints `cloud-universe.anycubic.com/p/p/workbench/api/...` pour le flux web.
2. Traiter les endpoints `api/...` (sans host explicite) comme dépendants du client mobile/contexte base URL.
3. Encadrer chaque appel avec timeout + retry borné (`429/5xx`) + logs sans secrets.
4. Valider systématiquement les payloads applicatifs (`code == 1` côté réponse JSON quand présent).

### Objectif
Centraliser la liste exploitable des endpoints Anycubic Cloud pour accélérer le dev, limiter les divergences d’implémentation et simplifier le troubleshooting.

---
