### But
Documenter les différents boutons de l’onglet `Files` et expliquer leur comportement réel (actif, stub, effets UI, flux cloud).

### Périmètre
- Onglet `Files` construit dans `app_gui_qt/tabs/files_tab.py`.
- Boutons toolbar + boutons des cartes fichier.

### Entrées
- Session cloud active.
- Callback de refresh (`on_refresh`) injecté par `app_gui_qt/app.py`.
- Liste `FileItem` reçue après refresh.

### Sorties attendues
- Compréhension claire de chaque bouton : action, état d’implémentation, message utilisateur.

### Boutons de la toolbar (haut de l’onglet)
1. **`Refresh`**
- Emplacement: barre d’actions de l’onglet.
- État: **actif**.
- Action:
  - Lance `FilesTab.refresh()`.
  - Exécute le callback cloud dans un thread (`files-refresh`).
  - Désactive temporairement le bouton pendant le chargement.
  - Met à jour quota + liste fichiers via `apply_refresh_result(...)`.
- Texte statut:
  - `Loading cloud data...` pendant chargement.
  - `Loaded N files from cloud API.` si succès.
  - Message d’erreur si exception ou erreur partielle.

2. **`Upload .pwmb`**
- Emplacement: barre d’actions de l’onglet.
- État: **stub UI**.
- Action actuelle:
  - Affiche une popup `Design only`.
  - Message: fonctionnalité prévue, non implémentée dans cet onglet.
- Note:
  - Le vrai upload fonctionnel passe aujourd’hui par le bouton global `Upload Dialog` (header), pas par ce bouton d’onglet.

### Boutons par carte fichier
1. **`Delete`**
- Emplacement: en haut à droite de chaque carte.
- État: **stub UI**.
- Action actuelle: popup `Design only`.

2. **`Details`**
- Emplacement: rangée d’actions de la carte.
- État: **actif**.
- Action actuelle:
  - Ouvre une boîte `File Details`.
  - Affiche les métadonnées consolidées (général, slicing, cloud).

3. **`Print`**
- Emplacement: rangée d’actions de la carte.
- État: **stub UI**.
- Action actuelle: popup `Design only`.

4. **`Download`**
- Emplacement: rangée d’actions de la carte.
- État: **stub UI**.
- Action actuelle: popup `Design only`.

5. **`Open 3D Viewer`**
- Emplacement: rangée d’actions, uniquement pour fichiers `.pwmb`.
- État: **actif conditionnel**.
- Condition:
  - Si callback `on_open_viewer` fourni: bouton connecté au viewer.
  - Sinon: bouton en mode stub.
- Implémentation actuelle dans l’app:
  - Le callback ouvre la boîte `3D Viewer Dialog`.

### Comportements liés (non-boutons mais visibles)
1. **Miniatures**
- Téléchargement asynchrone en arrière-plan (thread + semaphore).
- Cache disque optionnel via `CacheStore`.
- En cas d’échec: fallback visuel (extension + `100x100`).

2. **Résumé quota**
- Mis à jour après refresh:
  - `used / total`, `%`, `free`, nombre de fichiers.

### Contrats d’usage recommandés
1. Garder `Refresh` comme action principale de synchronisation cloud.
2. Marquer explicitement en UI les boutons encore stub pour éviter l’ambiguïté utilisateur.
3. Implémenter ensuite les actions réelles restantes dans cet ordre: `Download` -> `Delete` -> `Print` -> `Upload`.
4. Réutiliser les endpoints déjà documentés dans `13_ACLOUD_ENDPOINTS_CATALOG.md` et les règles de lecture dans `14_ACLOUD_ENDPOINT_RESPONSES_INTERPRETATION.md`.

### Objectif
Fournir une référence claire de l’onglet `Files` pour distinguer ce qui est déjà opérationnel de ce qui reste à implémenter.

---
