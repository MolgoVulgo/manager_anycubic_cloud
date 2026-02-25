# Reste à Faire

Date: 2026-02-23
Contexte: lots A (pipeline CPU contours/géométrie) et B (viewer OpenGL + wiring Files->Viewer) implémentés.

## Priorité 1 - Lot C

- [x] Brancher le cache 3D réel (contours + geometry) avec clés d'invalidation complètes.
- [x] Appliquer strictement les règles d'invalidation selon les paramètres build (`threshold`, `bin_mode`, strides, budgets, simplification, render mode).
- [x] Ajouter l'instrumentation perf CPU/GPU (`parse/decode/contours/triangulation/upload/draw`) avec logs stables.
- [x] Ajouter la gestion explicite des stages de progression (`read`, `decode`, `contours`, `geometry`, `upload`, `done`, `cache`) dans le viewer.
- [x] Rendre non-bloquant le chargement d'un fichier cloud pour le viewer (download async au lieu du callback synchrone).

## Priorité 1.5 - Lot D

- [x] Implémenter un rendu progressif 3D en 2 passes (contours d'abord, fill/triangulation ensuite).
- [x] Conserver les interactions viewport pendant la pass fill (aperçu contours déjà affiché).
- [x] Réutiliser le cache de contours entre les deux passes pour éviter un second decode/contours complet.

## Qualité Technique

- [ ] Renforcer la triangulation des polygones avec trous pour les cas non axis-alignés complexes.
- [ ] Implémenter/valider un tri back-to-front basé caméra pour les layers translucides.
- [ ] Ajouter une vraie stratégie de fallback renderer quand OpenGL init/upload échoue.
- [ ] Connecter la logique d'annulation (`CancellationToken`) au build 3D complet.
- [ ] Aligner le mode `index_strict` sur `color_index != 0` de façon stricte (aujourd'hui best-effort via intensité).

## Tests à Ajouter

- [x] Tests unitaires de cache/invalidation 3D.
- [x] Tests unitaires des métriques perf.
- [x] Tests unitaires du callback `open_viewer` avec résolution de fichier local/cache/download.
- [ ] Tests d'intégration du pipeline viewer (build async -> upload -> draw/ranges visibles).
- [ ] Goldens PWMB (`cube`, `cube2`, `misteer`) pour non-régression orientation/bbox/checksum.
- [ ] E2E minimal GUI: ouverture viewer depuis `Files`, rebuild, changement cutoff/stride sans rebuild CPU.

## UX Viewer

- [ ] Afficher des erreurs utilisateur plus explicites (parse/décodage/GL) avec actions de retry.
- [ ] Ajouter un indicateur clair "build en cours / source cache".
- [ ] Mémoriser les paramètres viewer (threshold, mode, stride, contour-only) entre ouvertures.
- [ ] Ajouter option d'ouverture directe d'un fichier local depuis le header principal.
