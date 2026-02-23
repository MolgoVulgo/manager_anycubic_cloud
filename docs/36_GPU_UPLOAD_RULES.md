### Règles
- Toute création/suppression VBO/VAO/EBO sur thread GL.
- Upload idempotent : reset puis apply.
- Ownership : après passage au renderer, les buffers CPU sont immuables.

### Fallback
- Si init/upload échoue : bascule CPU fallback, sans casser navigation/params.

---

