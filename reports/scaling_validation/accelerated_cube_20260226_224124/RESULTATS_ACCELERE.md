# Resultats Campagne Acceleree

## Perimetre execute
- Date: 2026-02-26
- Mode: accelere
- Corpus: `pwmb_files/cube.pwmb`
- Workers testes: `4,16,32`
- Runs par worker: `1`
- Politique parallele: `python_fanout`

## Artefacts principaux
- Summary JSON: `reports/scaling_validation/accelerated_cube_20260226_224124/scaling_validation_accelerated_cube.json`
- Summary Markdown: `reports/scaling_validation/accelerated_cube_20260226_224124/scaling_validation_accelerated_cube.md`
- Measurement workers=4: `reports/scaling_validation/accelerated_cube_20260226_224124/workers_04/measurement_protocol.md`
- Measurement workers=16: `reports/scaling_validation/accelerated_cube_20260226_224124/workers_16/measurement_protocol.md`
- Measurement workers=32: `reports/scaling_validation/accelerated_cube_20260226_224124/workers_32/measurement_protocol.md`

## Mesures clefs
| workers | gate_pass | diagnostic | cpu% moyen | idle% moyen | max si/so | native wall (ms) | opencv wall (ms) |
|---:|:---:|:---|---:|---:|---:|---:|---:|
| 4  | FAIL | memory_pressure | 245.50 | 92.00 | 48/90 | 12047.709 | 13819.323 |
| 16 | FAIL | memory_pressure | 295.61 | 92.00 | 48/90 | 12706.864 | 14405.071 |
| 32 | FAIL | memory_pressure | 308.50 | 92.00 | 48/90 | 12936.121 | 14481.754 |

## Lecture rapide
- Le protocole marque tous les runs `FAIL` sur gate de mesure a cause de `vmstat si/so` non nuls.
- Le diagnostic consolide `memory_pressure` sur les 3 workers.
- Sur ce corpus et ce contexte machine, le backend `cpp_native` reste plus rapide que `cpp_opencv`.
- Le summary global a `comparable_workers=[]`, donc validation finale de scaling non concluante dans ces conditions.

## Action recommandee avant campagne de reference
- Refaire une campagne apres assainissement memoire/swap (objectif: `si/so ~= 0` et `majflt/s ~= 0`) pour obtenir des runs comparables.
