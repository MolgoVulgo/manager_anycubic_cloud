# 53_lot_k_contours_quality - amelioration visuelle des contours (viewer 3D)

Date: 2026-02-25

## Contexte
Le ressenti "qualite basse" ne vient pas seulement du nombre de couches visibles (Z), mais aussi de l'aspect des contours en XY:
- extraction sur raster binaire (bords orthogonaux),
- sous-echantillonnage XY agressif en preview sur gros volumes.

Effet utilisateur: silhouettes "carrees"/abrupte meme quand beaucoup de layers sont affiches.

## Objectif
Ameliorer la perception de qualite des contours sans casser:
- la parite fonctionnelle (aires/bbox),
- la performance interactive du viewer,
- le contrat pipeline/backend deja stabilise.

## Lots proposes

### Lot 1 - Correctif rapide XY pour qualite percue (faible risque) [REALISE]
Objectif:
- eviter la degradation XY en mode `Qualite max (100%)`,
- limiter l'aliasing de sous-echantillonnage sur presets 66%/33%.

Changements:
- quality 100% -> `xy_stride=1` force dans le job viewer.
- downsampling XY dans `render3d_core.contours._build_mask`:
  - avant: sous-echantillonnage brut (`arr[::step, ::step]`),
  - apres: aggregation par blocs (`any/max pooling`) pour conserver les details fins.

Impact attendu:
- 100%: contours plus fideles (moins de sensation "pixelisee"),
- 66/33: moins de pertes de details fins que l'ancienne decimation.

### Lot 2 - Lissage de contours preview (risque moyen) [REALISE]
Objectif:
- adoucir les segments orthogonaux visibles sans toucher aux donnees source.

Implementation:
- post-traitement optionnel des loops applique dans le pipeline (`contour_smoothing_iterations`),
- active cote viewer avec `1` passe de smoothing,
- garde-fous geometriques:
  - conservation du signe (orientation),
  - derive aire bornee,
  - derive bbox bornee,
  - rejet du smoothing si controles non valides.
- invalidation cache dediee via suffixe de cle (`*_smooth_iN`).

### Lot 3 - Extraction subpixel (risque moyen/eleve) [REALISE]
Objectif:
- produire des contours moins "escaliers" en sortie extraction.

Implementation:
- ajout d'un selecteur `contour_extractor` dans le pipeline/backend:
  - `pixel_edges` (historique),
  - `subpixel_halfgrid` (nouveau),
  - `marching_squares` (alias compatible vers le chemin subpixel).
- extracteur subpixel:
  - reconstruit les coins en demi-pixel (half-grid) a partir des loops extraites,
  - conserve aire/bbox via garde-fous et re-echelle locale,
  - fallback automatique vers la boucle source en cas de derive non validee.
- integration viewer:
  - valeur par defaut `subpixel_halfgrid`,
  - surcharge possible via env `RENDER3D_CONTOUR_EXTRACTOR`.
- isolation cache:
  - cles dediees par extracteur (`*_ce_<extractor>`), cumulable avec smoothing (`*_smooth_iN`).

### Lot 4 - Variante OpenCV orientee smoothing (optionnel) [REALISE]
Objectif:
- evaluer si les approximations OpenCV ameliorent la forme percue.

Implementation:
- ajout du parametre OpenCV approximation cote C++/pybind/wrapper Python:
  - `GEOM_CPP_OPENCV_APPROX=simple|tc89_l1|tc89_kcos`,
  - forwarding runtime dans `extract_polygons(..., impl=\"opencv\", opencv_approx=...)`.
- extension des outils campagne:
  - `tools/render3d_baseline.py` et `tools/render3d_compare_backends.py` avec `--cpp-opencv-approx`,
  - nouvel outil de synthese `tools/render3d_opencv_approx_summary.py`.

Campagne executee (profil z4/xy4, corpus 3 fichiers Anycubic+Lychee):
- rapports source:
  - `reports/render3d_campaign_python_z4.json`
  - `reports/render3d_campaign_cpp_native_z4.json`
  - `reports/render3d_campaign_cpp_opencv_z4.json` (simple)
  - `reports/render3d_campaign_cpp_opencv_tc89_l1_z4_lotK4.json`
  - `reports/render3d_campaign_cpp_opencv_tc89_kcos_z4_lotK4.json`
- synthese:
  - `reports/render3d_campaign_opencv_approx_summary_z4_lotK4.json`
  - `reports/render3d_campaign_opencv_approx_summary_z4_lotK4.md`

Resultat:
- recommendation OpenCV approx: `simple`.
- `tc89_l1` et `tc89_kcos` montrent une forte derive de parite (aire/triangles) et un temps total plus eleve.
- decision maintenue:
  - backend par defaut global: `cpp(native)`,
  - si OpenCV est force: approximation par defaut `simple`.

### Lot 5 - Finition visuelle GPU (faible risque) [REALISE]
Objectif:
- reduire l'impression d'angles durs au draw.

Implementation:
- anti-aliasing GPU:
  - demande de multisampling sur le viewport OpenGL (`QSurfaceFormat.samples`),
  - activation GL multisample au runtime,
  - trace `requested/effective` dans les logs GPU.
- ajustement style draw orientee lisibilite:
  - contour plus lisible via epaisseur configurable (`line_width_px`, defaut `1.35`),
  - points de debug plus visibles (`point_size_px`, defaut `2.25`),
  - remplissage legerement desature en alpha (`fill_alpha_scale`, defaut `0.92`) pour laisser ressortir le contour.
- observabilite:
  - ajout des metriques GPU `msaa_samples`, `line_width_px`, `point_size_px`, `fill_alpha_scale`.

Configuration (optionnelle, via env):
- `RENDER3D_MSAA_SAMPLES` (0..8, defaut `4`)
- `RENDER3D_LINE_WIDTH_PX` (1.0..4.0, defaut `1.35`)
- `RENDER3D_POINT_SIZE_PX` (1.0..8.0, defaut `2.25`)
- `RENDER3D_FILL_ALPHA_SCALE` (0.25..1.0, defaut `0.92`)

## Criteres d'acceptation globaux
- Pas de regression de robustesse (pas de crash/exception viewer).
- Invariants geometriques dans tolerance (`area`, `bbox`) sur corpus.
- Amelioration visuelle constatee sur fichiers lourds (Anycubic + Lychee).
- Temps de build compatible usage interactif (profil logs `render3d.build`).

## References
- `docs/40_update_to_cpp.md`
- `docs/45_LOT_D_OPENCV_OPTION.md`
- `RESTE_A_FAIRE.md`
