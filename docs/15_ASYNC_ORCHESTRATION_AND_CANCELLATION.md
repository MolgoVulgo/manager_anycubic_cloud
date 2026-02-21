### Objectif
Ne jamais bloquer l’UI : build async + annulation + progress.

### Contrat progress
- `progress_cb(percent:int, stage:str)`
- stages normalisés :
  - `read`, `decode`, `contours`, `decimate`, `geometry`, `upload`, `done`, `cache`

### Annulation
- Token partagé (atomic bool / event).
- Checkpoints par job :
  - avant decode
  - après decode
  - avant triangulation
  - avant concat final

### Résultats
- Succès : `PwmbContourGeometry` prêt à upload.
- Cancel : sortie contrôlée, UI revient état stable.

---

