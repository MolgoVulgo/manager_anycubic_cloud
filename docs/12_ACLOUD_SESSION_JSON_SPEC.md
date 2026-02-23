# Format `session.json` (v2)

## But
Décrire le fichier `session.json` utilisé pour persister une session Anycubic Cloud.

## Emplacement
- Par défaut : `session.json` (racine projet / cwd de lancement)
- Override : `ACCLOUD_SESSION_PATH=/chemin/session.json`

## Permissions
- Mode strict : `0600` (lecture/écriture user uniquement)

## Structure canonique (actuelle)
```json
{
  "last_update": "23/02/2026",
  "tokens": {
    "Authorization": "Bearer <...>",
    "access_token": "<token>",
    "id_token": "<token>",
    "token": "<token>"
  }
}
```

### Notes
- `tokens` peut être partiel ; le mode robuste est avec `token` (`XX-Token`) ou `Authorization`.
- L'ordre/présence des clés de `tokens` varie selon l'import HAR.
- Le fichier est écrit en mode strict `0600`.

## Compatibilité chargement
Le loader accepte aussi des formes legacy, par exemple :
```json
{ "last_update": "DD/MM/YYYY", "tokens": {...}, "headers": {...} }
```
Alors :
- les tokens sont normalisés pour le runtime,
- des clés legacy (`Authorization`, `X-Access-Token`, `X-Auth-Token`) peuvent être reprises.
