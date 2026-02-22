### But
Documenter les differents boutons de l'onglet `Printer` et expliquer leur comportement reel (actif, stub, effets UI).

### Perimetre
- Onglet `Printer` construit dans `gui/tabs/printer_tab.py`.
- Boutons toolbar + boutons des cartes imprimante + bouton CTA lateral.

### Entrees
- Chargement de l'UI `build_printer_tab(...)`.
- Donnees statiques embarquees dans le code (3 imprimantes de demo).

### Sorties attendues
- Comprendre clairement chaque bouton: action, etat d'implementation, message utilisateur.

### Etat general de l'onglet
1. **Nature de l'onglet**
- Onglet de demonstration statique (phase design).
- Les actions ne sont pas connectees au backend cloud dans ce composant.

2. **Donnees affichees**
- Cartes imprimantes statiques (pas de refresh API reel dans cet onglet).
- Bloc `Preview Payload` en lecture seule (visuel uniquement).

### Boutons de la toolbar (haut de l'onglet)
1. **`Refresh printers`**
- Emplacement: barre d'actions en haut.
- Etat: **stub UI**.
- Action actuelle:
  - Affiche une popup `Design only`.
  - Aucune requete cloud lancee.

2. **`Add filter`**
- Emplacement: barre d'actions en haut.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

3. **`Bulk print check`**
- Emplacement: barre d'actions en haut.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

### Boutons par carte imprimante
Pour chaque carte (`Photon Mono M7 - Lab A`, `Photon Mono 4 - Rack 2`, `M5S Pro - QA`):

1. **`Open print dialog`**
- Emplacement: rangee d'actions de la carte.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

2. **`Live status`**
- Emplacement: rangee d'actions de la carte.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

3. **`Details`**
- Emplacement: rangee d'actions de la carte.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

### Bouton lateral (panneau droit)
1. **`Open Print Dialog`**
- Emplacement: bas du panneau `Preview Payload`.
- Etat: **stub UI**.
- Action actuelle: popup `Design only`.

### Comportements lies (non-boutons)
1. **Cartes metriques**
- `Online`, `Offline`, `Printing`, `Queued jobs`.
- Valeurs statiques de presentation, non liees a une telemetrie live.

2. **Preview Payload**
- JSON affiche dans `QPlainTextEdit` read-only.
- Texte explicitement marque comme visuel uniquement pour la phase 2.

### Clarification importante
- Le bouton global `Print Dialog` dans le header principal (hors onglet `Printer`) ouvre bien la boite de dialogue d'impression.
- Dans l'onglet `Printer` lui-meme, tous les boutons sont des stubs actuellement.

### Contrats d'usage recommandes
1. Garder cet onglet comme zone de preview tant que les callbacks backend ne sont pas branches.
2. Indiquer explicitement en UI qu'il s'agit de controles non operationnels.
3. Lors de l'implementation, brancher en priorite:
   - `Refresh printers` -> endpoint liste imprimantes
   - `Live status` -> endpoint status/etat imprimante
   - `Details` -> endpoint details imprimante/projet
   - `Open print dialog` -> ouverture du vrai flux print

### Objectif
Fournir une reference claire de l'onglet `Printer` pour distinguer l'UI de demonstration des comportements reellement implementes.

---
