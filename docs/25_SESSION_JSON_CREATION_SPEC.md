### But
Décrire la création du fichier `session.json` utilisé par l’application pour persister la session Anycubic Cloud.

### Entrées
- `SessionData.tokens` (tokens en mémoire).
- Chemin cible `session_path` (par défaut `session.json`, configurable via `ACCLOUD_SESSION_PATH`).

### Sorties attendues
- Fichier JSON valide, lisible par `load_session`.
- Permissions strictes sur le fichier (mode `0600`).

### Emplacement du fichier
1. **Par défaut**
- `session.json` dans le répertoire courant de lancement.

2. **Override environnement**
- Variable : `ACCLOUD_SESSION_PATH`
- Exemple : `/home/<user>/.config/manager_anycubic_cloud/session.json`

### Structure canonique (contrats)
Le fichier écrit par `save_session` contient :
1. `last_update`
- Format : `DD/MM/YYYY`.

2. `tokens`
- Objet JSON contenant uniquement les clés normalisées de stockage :
  - `id_token`
  - `token`
  - `access_token`
- Les valeurs sont stockées **sans** préfixe `Bearer `.

### Exemple de `session.json`
```json
{
  "last_update": "22/02/2026",
  "tokens": {
    "access_token": "<token>",
    "id_token": "<token>",
    "token": "<token>"
  }
}
```

### Procédure canonique de création
1. **Préparer le dossier parent**
- Créer le dossier parent si absent (`mkdir -p`).

2. **Normaliser les tokens pour stockage**
- Priorité runtime:
  - `access_token` <- `access_token` ou `Authorization` ou `token`
  - `id_token` <- `id_token` sinon fallback `access_token`
  - `token` <- `token` ou `X-Access-Token` ou `X-Auth-Token`
- Retirer `Bearer ` avant persistance.

3. **Construire le payload**
- `last_update = now.strftime("%d/%m/%Y")`
- `tokens = _normalize_tokens_for_storage(...)`

4. **Écrire atomiquement avec permissions strictes**
- Ouvrir le fichier avec `os.open(..., 0o600)`.
- Écrire JSON avec:
  - `ensure_ascii=true`
  - `indent=2`
  - `sort_keys=true`

### Lecture et compatibilité
1. **Lecture nominale**
- `load_session` lit `tokens` puis normalise pour runtime.
- En runtime, `Authorization` est reconstruit si nécessaire.

2. **Compatibilité legacy**
- Si ancien format avec `headers`, récupération de:
  - `Authorization`
  - `X-Access-Token`
  - `X-Auth-Token`
- Si clés top-level (`access_token`, `id_token`, `token`, `Authorization`), elles sont aussi absorbées.

### Règles de sécurité
- Ne jamais commiter `session.json`.
- Ne jamais logger les tokens complets.
- Appliquer masquage en logs (`abcd...wxyz`).
- Garder permissions `0600` uniquement (propriétaire lecture/écriture).

### Validation minimale
- Le fichier existe et est un JSON objet.
- `tokens` est un objet JSON.
- Au moins un token non vide si session authentifiée.
- `auth_headers()` doit produire `Authorization: Bearer <token>` après chargement.

### Objectif
Garantir une persistance de session stable, compatible et sécurisée pour réutiliser l’authentification cloud entre les exécutions.

---
