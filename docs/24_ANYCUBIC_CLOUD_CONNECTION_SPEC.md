### But
Définir un flux standard, fiable et auditable pour la connexion au **cloud Anycubic** depuis l’outil (authentification, session, renouvellement, erreurs).

### Entrées
- Identifiants utilisateur (email/téléphone + mot de passe) **ou** token déjà extrait.
- Configuration runtime : `base_url`, `region`, `device_id`, `client_version`.
- Horloge système valide (requise pour TTL/expiration).

### Sorties attendues
- Session authentifiée prête pour les appels API cloud.
- `access_token` actif + `refresh_token` (si fourni).
- Contexte de session : expiration, région, user/device bind.

### URLs à utiliser
1. **OAuth authorize (UC)**
- `GET https://uc.makeronline.com/login/oauth/authorize`
- Query observée :
  - `client_id=672efcd4ec11a66c8513`
  - `response_type=code`
  - `redirect_uri=https://cloud-universe.anycubic.com/login`
  - `scope=read`
  - `state=ac_web`

2. **Base API Cloud**
- `https://cloud-universe.anycubic.com`

3. **Exchange code -> id_token**
- `GET /p/p/workbench/api/v3/public/getoauthToken?code=<oauth_code>`
- URL complète :
  - `https://cloud-universe.anycubic.com/p/p/workbench/api/v3/public/getoauthToken?code=<oauth_code>`

4. **Login avec access token**
- `POST /p/p/workbench/api/v3/public/loginWithAccessToken`
- URL complète :
  - `https://cloud-universe.anycubic.com/p/p/workbench/api/v3/public/loginWithAccessToken`

5. **Validation session (léger)**
- `POST /p/p/workbench/api/work/index/getUserStore`
- URL complète :
  - `https://cloud-universe.anycubic.com/p/p/workbench/api/work/index/getUserStore`

### Pré-requis (contrats)
1. **Endpoints cohérents**
- URL cloud correspondant à la région cible.
- Version API connue/compatible.

2. **Identité client stable**
- `device_id` constant par installation.
- En-têtes client normalisés (`User-Agent`, version app, plateforme).

3. **Sécurité transport**
- HTTPS obligatoire.
- Validation TLS active (pas de bypass).

### Procédure canonique (contrats)
1. **Init session HTTP**
- Créer client HTTP avec timeout explicite (connexion/lecture).
- Définir en-têtes communs et corrélation (`X-Request-Id` si disponible).

2. **Auth login (ou bootstrap token)**
- Démarrer OAuth sur `uc.makeronline.com` pour récupérer `code`.
- Échanger `code` via `getoauthToken` pour obtenir `id_token`.
- Envoyer `id_token` sur `loginWithAccessToken`.
- Accepter uniquement réponses succès (`200/201` et `code == 1` côté payload).

3. **Extraire et normaliser les tokens**
- Lire `access_token`, `refresh_token`, `token_type`, `expires_in` ou `token` selon payload.
- Normaliser `Authorization: Bearer <access_token>`.
- Calculer `expires_at = now + expires_in` avec marge de sécurité.

4. **Valider la session**
- Appeler `getUserStore` (ou endpoint léger authentifié équivalent).
- Si `401/403`, invalider session et passer en stratégie de refresh/relogin.

5. **Persister le contexte minimal**
- Stocker uniquement : token, refresh token, expiration, région, device_id.
- Éviter tout stockage de mot de passe en clair.

6. **Renouvellement token**
- Déclencher refresh avant expiration (ex: marge 120s).
- Si refresh échoue (token révoqué/expiré), relancer login complet.

### Politique de retry
- Retry uniquement sur erreurs réseau/transitoires (`429`, `5xx`, timeout).
- Backoff exponentiel avec jitter.
- Pas de retry aveugle sur `401/403` (nécessite refresh/relogin).

### Gestion d’erreurs
- `400`: payload invalide -> corriger requête.
- `401/403`: auth invalide/expirée -> refresh puis relogin.
- `404`: mauvais endpoint/région.
- `429`: throttling -> backoff et plafonnement.
- `5xx`: incident cloud -> retry borné + journalisation.

### Sécurité
- Ne jamais journaliser un token complet.
- Masquer secrets dans logs (`abcd...wxyz`).
- Chiffrer le stockage local des tokens si possible.
- Purger immédiatement credentials temporaires en mémoire.

### Observabilité minimale
- `request_id`, endpoint, code HTTP, latence, tentative retry.
- Horodatage login/refresh + cause d’échec.
- Compteurs : taux de succès login, taux de refresh, erreurs 401/429.

### Format d’état recommandé
```json
{
  "cloud_base_url": "https://cloud-universe.anycubic.com",
  "region": "us-east-2|...",
  "device_id": "...",
  "token_type": "Bearer",
  "access_token": "<redacted-or-runtime-only>",
  "refresh_token": "<optional>",
  "expires_at": "ISO-8601",
  "last_login_at": "ISO-8601",
  "last_refresh_at": "ISO-8601"
}
```

### Objectif
Garantir une connexion Anycubic Cloud stable et robuste, avec gestion propre du cycle de vie des tokens et comportement déterministe en cas d’erreur réseau/auth.

---
