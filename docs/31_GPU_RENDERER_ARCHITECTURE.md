### Objectif
- Rendu 3D **GPU-first**.
- CPU : build + fallback.

### Rôles
- **CPU Builder** : decode → mask → loops → geometry buffers.
- **GPU Renderer** : upload buffers → draw (tri/line/point).
- **CPU Fallback** : rendu simplifié / debug / oracle even-odd.

### Invariants
- OpenGL (création/upload/draw) = **thread GL uniquement**.
- Les buffers GPU proviennent d’une structure immuable (`PwmbContourGeometry`).

---

