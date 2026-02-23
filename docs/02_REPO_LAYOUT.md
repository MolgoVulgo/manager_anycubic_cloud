# Structure repo recommandée (v2)

But : découpler le code généré en **couches** (testables, sans UI), puis brancher une GUI simple au-dessus.

## Modules
- `accloud_core/` : client HTTP + session + endpoints + modèles
- `pwmb_core/` : parser container + tables + décodage images + contours/geometry builder
- `render3d_core/` : renderer (CPU/GPU), buffers, draw pipeline
- `app_gui_qt/` : UI Qt (onglets, bindings, threads UI)

## Dépendances (sens unique)
`app_gui_qt` -> `accloud_core`, `pwmb_core`, `render3d_core`

`render3d_core` -> `pwmb_core` (consomme contours/géométrie)

Aucun import inverse autorisé (sinon mélange core/UI).
