### API logique (sans imposer l’impl)
- `read_pwmb_document(path) -> PwmbDocument`
- `decode_layer(doc, layer_index) -> np.ndarray[uint8] (W*H)`
- `export_layers_to_png(doc, out_dir, threshold=None)`

### Sémantique pixel
- `0` : vide
- `255` : matière pleine
- `1..254` : intermédiaires (AA / grayscale)

### Binarisation
- `mask = (img >= threshold)`
- `threshold` doit être explicitement configuré.

### Politique d’erreurs
- Erreurs structurelles (signature/version/offsets) : stop.
- Erreurs couche : skip / noir + log, continuer.

### Performance
- Lecture via mmap.
- Ne jamais conserver les images `W*H` de toutes les couches en RAM.

---

