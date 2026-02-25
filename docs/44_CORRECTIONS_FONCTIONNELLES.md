# 44_corrections_fonctionnelles - post lots A/B/C

## Objectif
Tracer les corrections fonctionnelles appliquees apres les lots A/B/C, avec impact direct sur la qualite de rendu 3D en production.

## 1) Correction decode PW0 multi-variant (Anycubic officiel + Lychee)

### Probleme observe
- Sur certains PWMB tiers (ex: Lychee), les premieres couches etaient correctes puis le rendu derivait en grands rectangles couvrant presque toute la surface.
- Les PWMB issus du logiciel officiel Anycubic ne presentaient pas ce symptome.

### Cause racine
- Le decodeur PW0 supposait un seul format (`word16`), alors que des fichiers tiers utilisent une variante tokenisee (`byte_token`) compatible avec l'ancien decodeur historique.
- Le pipeline de contours appelait `decode_layer(..., strict=False)`, ce qui laissait passer des decodages semantiquement faux sans exception.

### Correction appliquee
- Ajout de deux variantes PW0 dans `pwmb_core.decode_pw0`:
  - `word16`
  - `byte_token`
- Ajout d'une selection adaptative dans `pwmb_core.container.decode_layer`:
  - evaluation de l'erreur de decode par rapport a `LayerDef.non_zero_pixel_count`,
  - fallback automatique vers l'autre variante en cas d'ecart important,
  - memorisation de la variante retenue dans `PwmbDocument.pw0_variant`.
- Ajout de logs de selection de variante:
  - event `pwmb.decode_pw0_variant_selected`.

## 2) Correction ergonomie/observabilite layer cutoff

### Evolution UI
- Le controle `Layer cutoff` affiche maintenant explicitement le numero de couche courant et le maximum:
  - format: `L<current> / <max>`.

### Evolution logs render
- Les logs de draw GPU incluent desormais `cutoff_layer` pour corréler les mesures draw avec le niveau de coupe applique.

## 3) Impact fonctionnel attendu
- Suppression des artefacts "rectangles pleins" sur les PWMB tiers impactes.
- Maintien du comportement stable sur les PWMB officiels.
- Diagnostic plus rapide des problemes de rendu via:
  - variante PW0 selectionnee,
  - cutoff effectivement applique au draw.

## 4) Validation
- Tests unitaires PW0:
  - decodage explicite `byte_token`,
  - rejet variante inconnue.
- Test integration PWMB:
  - fallback automatique vers `byte_token` sur payload synthetique dedie.
- Validation manuelle sur corpus raven (fichier officiel + fichier Lychee) avec verification des non-zero counts decoded vs metadata.
