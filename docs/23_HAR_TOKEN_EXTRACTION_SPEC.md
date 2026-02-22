### But
Décrire une méthode reproductible pour extraire, depuis un fichier **HAR**, les données nécessaires à la génération/utilisation du token d’authentification Anycubic Cloud.

### Entrée
- Fichier `*.har` exporté depuis le navigateur (Network → Save all as HAR).
- Session où la connexion Anycubic Cloud a réussi.

### Sorties attendues
- `access_token` (ou bearer token équivalent).
- `refresh_token` (si présent).
- Métadonnées utiles : `expires_in`, `token_type`, horodatage de capture.

### Procédure canonique (contrats)
1. **Charger le HAR**
- Parser JSON racine `log.entries[]`.
- Ignorer les entrées sans `request.url`.

2. **Filtrer les requêtes d’auth**
- Garder les URLs contenant des motifs typiques :
  - `/login`
  - `/auth`
  - `/token`
  - `/refresh`
- Priorité aux requêtes `POST` avec `request.postData`.

3. **Extraire les artefacts côté requête**
- `request.headers[]` : chercher `Authorization`, `X-Auth-Token`, `Bearer`.
- `request.postData.text` : parser JSON/form-data si présent.
- Capturer aussi `deviceId`, `client_id`, `grant_type` si disponibles.

4. **Extraire les artefacts côté réponse**
- `response.content.text` : parser JSON.
- Rechercher les clés :
  - `access_token`
  - `refresh_token`
  - `token`
  - `expires_in`
  - `token_type`
- Si `content.encoding == "base64"`, décoder avant parse JSON.

5. **Normaliser le token**
- Si la valeur commence par `Bearer `, stocker :
  - `raw_auth_header` (valeur complète)
  - `access_token` (sans préfixe `Bearer `)
- Normaliser espaces et retours ligne.

6. **Valider la cohérence**
- Token non vide.
- Longueur plausible (ex: `>= 32`).
- Réponse HTTP succès (`status` 200/201).
- Si `expires_in` présent, calculer `captured_at + expires_in`.

### Règles de priorité
1. Token dans **response JSON** d’une route de login/token.
2. Token dans **header Authorization** d’une requête immédiatement suivante.
3. Token dans cookie/session uniquement en fallback.

### Cas limites
- Plusieurs logins dans le même HAR : prendre la dernière séquence login réussie.
- HAR tronqué : conserver l’entrée la plus complète (request + response).
- Rotation de token : conserver `latest_valid_token` + historique minimal.

### Sécurité
- Ne jamais commiter un HAR brut contenant credentials/tokens.
- Masquer tokens dans logs (`abcd...wxyz`).
- Purger `email`, `password`, cookies et identifiants sensibles après extraction.

### Format de sortie recommandé
```json
{
  "source": "capture.har",
  "captured_at": "ISO-8601",
  "auth_endpoint": "https://.../auth/login",
  "token_type": "Bearer",
  "access_token": "<redacted-or-runtime-only>",
  "refresh_token": "<optional>",
  "expires_in": 3600,
  "expires_at": "ISO-8601"
}
```

### Objectif
Obtenir un pipeline d’extraction HAR fiable, déterministe et auditable pour alimenter l’authentification côté outil sans dépendre d’une capture manuelle ad hoc.

---
