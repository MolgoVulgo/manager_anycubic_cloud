### Buffers canoniques
- Triangles : `triangle_vertices` shape `(T,4)` float32 (`x,y,z,layer_id`)
- Lignes : `line_vertices` shape `(L,4)` float32
- Points : `point_vertices` shape `(P,4)` float32

### Ranges par layer
Pour chaque layer `i`, stocker :
- `tri_range[i] = (start, count)`
- `line_range[i] = (start, count)`
- `point_range[i] = (start, count)`

### Shaders (attributs minimum)
- `a_pos: vec3`
- `a_layer: float/int`
- `u_mvp: mat4`
- `u_color: vec4`
- `u_shade_kind: int` (fill/edge/point)

---

