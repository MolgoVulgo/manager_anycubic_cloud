# Ordre de lecture et génération (v2)

Objectif : permettre une génération de code **déterministe** (Codex) en construisant d’abord les **cores** (Anycubic Cloud + PWMB + moteur 3D), puis seulement la **GUI**.

## Règle
- **Core d’abord** (types, IO, décodage, géométrie, renderer, orchestration, perf).
- **UI à la fin** (Qt/onglets/boutons), en simple consommateur du core.

## Ordre recommandé
1. Conventions globales (vérité, temps, sécurité, erreurs)
2. Anycubic Cloud (auth/session/endpoints/réponses)
3. PWMB (container/tables/structs/decoders)
4. 3D (contours→géométrie→renderer, puis GPU/perf/cache)
5. UI (Files tab, Printer tab)
6. Refactor guide & tests
7. Lots migration C++ (40..52), dont runbook campagne `z1/xy1`

## Mapping depuis docs.zip (v1 -> v2)
- Anycubic : 23/24/25/26/27/28/29/30 => 10..17
- PWMB : 00/01/02/03/04/05/06/07/09/19 => 20..29
- 3D/GPU : 08/11/12/13/14/15/16/17/21/22 => 30..39
- Refactor : 10 => 90
