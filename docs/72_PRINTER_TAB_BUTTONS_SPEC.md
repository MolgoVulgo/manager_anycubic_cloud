### But
Documenter les differents boutons de l'onglet `Printer` et expliquer leur comportement reel (actif, stub, effets UI).

### Perimetre
- Onglet `Printer` construit dans `app_gui_qt/tabs/printer_tab.py`.
- Boutons toolbar + boutons des cartes imprimante + bouton CTA lateral.

### Entrees
- Chargement de l'UI `build_printer_tab(...)`.
- Callback `on_refresh` (optionnel) pour chargement cloud.
- Fallback demo: donnees statiques embarquees si aucun callback n'est fourni.

### Sorties attendues
- Comprendre clairement chaque bouton: action, etat d'implementation, message utilisateur.

### Etat general de l'onglet
1. **Nature de l'onglet**
- Onglet fonctionnel cote UI avec integration callback cloud (`on_refresh`) quand configure.
- En l'absence de callback: mode demo statique (3 imprimantes pre-remplies).

2. **Donnees affichees**
- Cartes imprimantes dynamiques apres refresh cloud (ou demo locale si pas de callback).
- Les cartes affichent aussi les infos job quand disponibles: nom du fichier, progression, temps ecoule, temps restant, couches courante/total.
  - Sources des infos job:
    - `GET /p/p/workbench/api/work/printer/getPrinters` (bloc `project` si present).
    - `GET /p/p/workbench/api/work/project/getProjects` (tentative `print_status=1`, puis fallback sans filtre si vide).
  - En cas de reponse vide sur `getProjects`, l'UI conserve les infos job deja presentes dans `getPrinters` au lieu de les effacer.
- Bloc `Preview Payload` en lecture seule, mis a jour avec l'imprimante selectionnee.

### Boutons de la toolbar (haut de l'onglet)
1. **`Refresh printers`**
- Emplacement: barre d'actions en haut.
- Etat: **actif**.
- Action actuelle:
  - Lance `PrinterTab.refresh()`.
  - Execute le callback cloud dans un thread (`printers-refresh`).
  - Met a jour cartes/metriques/payload via `render_printers(...)`.
  - Un auto-refresh periodique est aussi actif en mode app principal (toutes les 30 secondes).

### Boutons par carte imprimante
Pour chaque carte imprimante affichee (cloud ou demo):

1. **`Details`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.
- Action actuelle: ouvre une boite `Printer Details` avec details complets en lecture seule.

### Bouton lateral (panneau droit)
1. **Aucun bouton d'action**
- Le panneau `Preview Payload` reste en lecture seule (sans bouton de lancement).

### Comportements lies (non-boutons)
1. **Cartes metriques**
- `Online`, `Offline`, `Printing`, `Jobs history`.
- Valeurs recalculees a chaque `render_printers(...)` selon les donnees chargees.

2. **Preview Payload**
- JSON affiche dans `QPlainTextEdit` read-only.
- Payload de preview mis a jour selon la selection courante (printer_id/printer_name + champs job: fichier, progression, temps ecoule/restant).

### Clarification importante
- Le bouton global `Print Dialog` dans le header principal (hors onglet `Printer`) ouvre la boite de dialogue d'impression.
- Dans l'onglet `Printer`, l'objectif est le monitoring (etat + metriques + payload), sans action de lancement direct.

### Contrats d'usage recommandes
1. Brancher `on_refresh` sur `AnycubicCloudApi.list_printers()` pour un mode cloud complet.
2. Garder l'appel d'enrichissement projets (`getProjects`) actif pour completer les infos de job en cours.
3. Conserver le mode demo comme fallback si aucun callback n'est configure.

### Objectif
Fournir une reference claire de l'onglet `Printer` pour distinguer l'UI de demonstration des comportements reellement implementes.

---
