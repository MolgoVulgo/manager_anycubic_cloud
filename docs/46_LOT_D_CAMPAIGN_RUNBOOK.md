# 46_lot_d_campaign_runbook - execution campagne render3d (z1/xy1)

## Objectif
Documenter la procedure standard pour lancer la campagne corpus complete en qualite max:
- `xy_stride=1`
- `z_stride=1`
- comparaison des 2 variantes C++:
  - `cpp(native)`
  - `cpp(opencv)`

Cette campagne produit les rapports de base par backend et un rapport de synthese avec decision.

## Prerequis
- Repository positionne sur:
  - `/home/kaj/Develop/python/manager_anycubic_cloud`
- Module C++ disponible (`GEOM_BACKEND=cpp` fonctionnel).
- Variante OpenCV disponible si comparaison `cpp(opencv)` souhaitee
  (build `pwmb_geom_cpp` avec `-DWITH_OPENCV=ON`).
- Corpus present dans `pwmb_files/` (ou autre dossier passe en argument).

## Script recommande
Script unique:
- `tools/run_campaign_z1_xy1.sh`

Execution par defaut:
```bash
cd /home/kaj/Develop/python/manager_anycubic_cloud
./tools/run_campaign_z1_xy1.sh
```

Execution avec chemins explicites:
```bash
./tools/run_campaign_z1_xy1.sh <corpus_dir> <reports_dir>
```

Exemple:
```bash
./tools/run_campaign_z1_xy1.sh pwmb_files reports
```

## Etapes executees par le script
1. baseline `cpp(native)`:
   - `--backend cpp --cpp-contours-impl native`
2. baseline `cpp(opencv)`:
   - `--backend cpp --cpp-contours-impl opencv`
3. consolidation:
   - `tools/render3d_campaign_summary.py`

## Fichiers de sortie attendus
- `reports/render3d_campaign_cpp_native_z1_xy1.json`
- `reports/render3d_campaign_cpp_opencv_z1_xy1.json`
- `reports/render3d_campaign_summary_z1_xy1.json`
- `reports/render3d_campaign_summary_z1_xy1.md`

## Interpretation et decision
Le fichier principal de lecture est:
- `reports/render3d_campaign_summary_z1_xy1.md`

Decision attendue:
- verifier parite fonctionnelle (`mesh_area`, `contour_area`, `bbox`, `triangle_count`)
- comparer les temps agreges (`decode`, `contours`, `triangulation`, `total`)
- confirmer ou ajuster la valeur par defaut `native|opencv`.

## Notes d execution
- Cette campagne peut etre longue sur gros corpus (plusieurs dizaines de minutes).
- En cas de run interrompu, relancer le script complet pour garder un protocole homogene.
