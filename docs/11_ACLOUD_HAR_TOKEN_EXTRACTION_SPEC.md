# Extraction de session depuis un HAR (v2)

## But
Importer un `.har` (DevTools Network) et extraire une session réutilisable :
- `tokens` applicatifs (`token`, `id_token`, `access_token`, `Authorization` si dérivable)

## Entrée
- Fichier HAR standard : `log.entries[*].request|response`

## Sortie
- Objet runtime : `SessionData(tokens={...})`

## Pipeline canonique (contrat)
1) Charger le JSON HAR.
- Erreur si JSON invalide ou structure sans `log.entries`.

2) Parcourir `entries`.
- Normaliser `request.url`, `request.method`, `response.status`.
- Ignorer les entrées sans URL.

3) Extraire les tokens (priorités)
- Source principale : `response.content.text` JSON
  - chercher `data.id_token`
  - chercher `data.token`
- chercher `access_token` et champs proches si présents

4) Sources secondaires (best effort)
- Headers requête (`Authorization`, `X-Access-Token`, `X-Auth-Token`, `X-*token*`)
- Query params token-like (fallback)

5) Normaliser
- Normaliser les tokens pour le runtime (`Authorization` peut être dérivé depuis `access_token`).
- Le stockage disque garde un sous-ensemble compatible (`save_session`).

6) Écrire `session.json`
- voir `12_ACLOUD_SESSION_JSON_SPEC.md`
- permissions fichier : `0600`

## Contrat sécurité
- Masquer systématiquement tokens/secrets dans logs.
- Interdire le commit de `session.json`.
