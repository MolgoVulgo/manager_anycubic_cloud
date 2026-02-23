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
- Bloc `Preview Payload` en lecture seule, mis a jour avec l'imprimante selectionnee.

### Boutons de la toolbar (haut de l'onglet)
1. **`Refresh printers`**
- Emplacement: barre d'actions en haut.
- Etat: **actif**.
- Action actuelle:
  - Lance `PrinterTab.refresh()`.
  - Execute le callback cloud dans un thread (`printers-refresh`).
  - Met a jour cartes/metriques/payload via `render_printers(...)`.

2. **`Add filter`**
- Emplacement: barre d'actions en haut.
- Etat: **actif**.
- Action actuelle:
  - Affiche/masque un filtre (`All/Online/Printing/Offline`).
  - Applique le filtrage des cartes sans appel reseau.

3. **`Bulk print check`**
- Emplacement: barre d'actions en haut.
- Etat: **actif**.
- Action actuelle:
  - Calcule un resume (`loaded/online/printing/idle/offline`).
  - Affiche le resultat dans une popup.

### Boutons par carte imprimante
Pour chaque carte imprimante affichee (cloud ou demo):

1. **`Open print dialog`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif conditionnel**.
- Action actuelle:
  - Selectionne l'imprimante.
  - Ouvre le vrai print dialog si callback `on_open_print_dialog` fourni.
  - Sinon affiche "No print dialog callback configured.".

2. **`Live status`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.
- Action actuelle: affiche un snapshot statut (online/state/printing/reason/device status/last sync).

3. **`Details`**
- Emplacement: rangee d'actions de la carte.
- Etat: **actif**.
- Action actuelle: ouvre une boite `Printer Details` avec details complets en lecture seule.

### Bouton lateral (panneau droit)
1. **`Open Print Dialog`**
- Emplacement: bas du panneau `Preview Payload`.
- Etat: **actif conditionnel**.
- Action actuelle:
  - Ouvre le flux print pour l'imprimante selectionnee (meme logique que le bouton carte).

### Comportements lies (non-boutons)
1. **Cartes metriques**
- `Online`, `Offline`, `Printing`, `Queued jobs`.
- Valeurs recalculees a chaque `render_printers(...)` selon les donnees chargees.

2. **Preview Payload**
- JSON affiche dans `QPlainTextEdit` read-only.
- Payload de preview mis a jour selon la selection courante (printer_id/printer_name).

### Clarification importante
- Le bouton global `Print Dialog` dans le header principal (hors onglet `Printer`) ouvre bien la boite de dialogue d'impression.
- Dans l'onglet `Printer`, les controles sont operationnels cote UI; la partie backend depend des callbacks injectes.

### Contrats d'usage recommandes
1. Brancher `on_refresh` sur `AnycubicCloudApi.list_printers()` pour un mode cloud complet.
2. Fournir `on_open_print_dialog` pour connecter les CTA printer au vrai flux print.
3. Conserver le mode demo comme fallback si aucun callback n'est configure.

### Objectif
Fournir une reference claire de l'onglet `Printer` pour distinguer l'UI de demonstration des comportements reellement implementes.

---
