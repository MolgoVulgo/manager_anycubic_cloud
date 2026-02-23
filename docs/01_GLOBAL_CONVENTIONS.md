# Conventions globales (v2)

## 1) Statut de vérité (à utiliser partout)
Chaque assertion “factuelle” doit être taguée :

- **OBSERVED(HAR)** : vu dans une capture HAR.
- **OBSERVED(LOG)** : vu dans des logs applicatifs.
- **OBSERVED(CODE-LEGACY)** : confirmé dans l’app legacy.
- **INFERRED** : déduit d’un modèle / mapping, non capturé.
- **UNVERIFIED** : hypothèse en attente de validation.

## 2) Temps / dates
- Format canonique machine : **ISO-8601** avec timezone (ex: `2026-02-22T12:34:56+01:00`).
- Format UI (optionnel) : `DD/MM/YYYY` (affichage uniquement).
- Toute persistance (session/cache) doit utiliser ISO-8601.

## 3) Sécurité / redaction logs
Ne jamais loguer en clair :
- Cookies (`Cookie`, `Set-Cookie`)
- Tokens (`Authorization`, `XX-Token`, `access_token`, `id_token`, `refresh_token`, `token`)
- Signatures/nonce/horodatage : `XX-Signature`, `XX-Nonce`, `XX-Timestamp` (et équivalents)
- Identifiants perso : email/téléphone/user_id si présent

Règle simple : si le nom de clé contient `token`, `cookie`, `signature`, `nonce` → **[REDACTED]**.

## 4) Contrat d’erreurs API (Anycubic)
Décision = HTTP + payload applicatif :

- HTTP `2xx` + `code==1` => succès métier.
- HTTP `429`/`5xx` => retry borné + backoff.
- HTTP `401/403` => session invalide/expirée => refresh/reimport HAR.
- JSON invalide => erreur API (non exploitable).
- `code != 1` => erreur métier, message = `msg`/`message`/`error`.

## 5) Contrat d’erreurs IO (PWMB)
- Offsets hors bornes / incohérences table => erreur parse.
- Décodage couche : tout dépassement ou sous-consommation => erreur décodage (pas de “best effort” silencieux).
