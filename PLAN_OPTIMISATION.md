# PLAN_OPTIMISATION

Objectif : obtenir un scaling multi-core réel (CPU machine non-idle, %CPU process qui grimpe avec workers, wall qui baisse) en éliminant les faux signaux (swap, copies, GIL, oversubscription).

---

## 1) Verrouiller un protocole de mesure propre (sinon tu optimises du swap/bruit)

### 1.1 Outillage minimal

* Installer les outils de mesure :

  * `sysstat` (pidstat)
  * `perf` (ou linux-tools)

Commandes :

```bash
sudo pacman -S sysstat
sudo pacman -S perf || sudo pacman -S linux-tools
```

Si `perf` est bridé :

```bash
sudo sysctl kernel.perf_event_paranoid=1
sudo sysctl kernel.kptr_restrict=0
```

### 1.2 Run reproductible (mêmes conditions, sinon chiffres inutiles)

* Machine “propre” : fermer ce qui consomme RAM/CPU.
* Objectif : **0 swap-in/out** pendant la fenêtre de mesure.
* 3 runs minimum par variante (moyenne + écart) pour éviter la variance cache/mémoire.

### 1.3 Capture standard pendant run (toujours les mêmes points)

* Affinité + threads :

```bash
pid=<PID>
taskset -pc $pid
cat /proc/$pid/status | egrep 'Cpus_allowed_list|Threads'
ps -L -p $pid -o pid,tid,psr,pcpu,comm --sort=-pcpu | head -n 30
```

* CPU/RSS/fautes + paging :

```bash
pidstat -r -u -p $pid 1
vmstat 1
```

* Hotspot CPU :

```bash
sudo perf top -p $pid
```

### 1.4 Gates “qualité de mesure”

* Si `vmstat` montre `si/so` qui bouge ou `pidstat` montre `majflt/s` notable → résultats contaminés.
* Tu ne compares pas des runs tant que ce gate n’est pas OK.

---

## 2) Prouver où est le goulot (GIL / natif sériel / mémoire)

### 2.1 GIL / orchestration Python

Symptômes :

* `perf top` dominé par `PyEval_*`, `take_gil`, `ceval`, etc.
* %CPU process plafonne ~100–200% même avec workers élevés.

Vérifs :

* `perf top -p $pid`
* `pidstat -u -p $pid 1` en faisant varier le nb de workers

### 2.2 Natif sériel (C++ fait un gros bloc mono-thread)

Symptômes :

* `perf top` dominé par symboles du `.so` natif, mais %CPU process reste bas.
* CPU machine très idle.

Vérifs :

* Localiser le `.so` puis voir les libs liées (OpenMP/TBB) :

```bash
python - <<'PY'
import pwmb_geom
print(pwmb_geom.__file__)
PY
ldd /chemin/vers/_pwmb_geom*.so | egrep 'gomp|omp|tbb|pthread'
```

### 2.3 Mémoire / copies / paging

Symptômes :

* swap non nul + `majflt/s` > 0
* `vmstat`: `si/so` actifs
* wall ne baisse pas malgré CPU cumulé qui baisse

Vérifs :

* `vmstat 1`
* `pidstat -r -p $pid 1`
* (option) instrumenter le code : taille des buffers, nb de concat, pics RSS

### 2.4 Gate “diagnostic prouvé”

* Tu dois pouvoir dire :

  * « c’est le GIL » OU « c’est le C++ sériel » OU « c’est la mémoire/copies »
* Sans ça, toute optimisation est probabiliste.

---

## 3) Forcer le parallélisme au bon niveau (C++ ou Python, mais pas les deux au hasard)

### Règle

* Un seul niveau de parallélisme effectif :

  * soit **C++ multithread interne** (recommandé si natif déjà présent)
  * soit **Python fan-out** (chunking) + natif qui relâche le GIL
* Sinon : oversubscription + jitter + wall incohérente.

### Option A — Parallélisme dans le C++ (TBB/OpenMP)

Actions :

1. Libérer le GIL autour du compute natif (obligatoire si appel depuis Python) :

   * pybind11 : `py::gil_scoped_release`
   * CPython : `Py_BEGIN_ALLOW_THREADS`
2. Paralléliser le hot loop en natif :

   * par ranges de layers (chunk)
   * ou par polygones/loops si peu de layers
3. Fixer explicitement le nb de threads (sinon runtime peut se brider) :

   * OpenMP : `OMP_NUM_THREADS`, `OMP_PROC_BIND`, `OMP_PLACES`
   * TBB : `task_arena` / contrôle threads selon implémentation
4. Côté Python : **1 worker** sur cette étape (pas de pool concurrent qui double la charge).

Gates :

* %CPU process monte fortement (ex : 800–2500% selon charge)
* CPU machine idle chute
* wall baisse jusqu’à un plateau

### Option B — Parallélisme côté Python (chunking) + natif GIL-free

Actions :

1. Chunking : `K layers par tâche` (8–32) au lieu de `1 layer = 1 future`
2. Un seul executor global (pas de pools imbriqués)
3. Assemblage final préalloué (0 concat sur gros buffers)
4. Natif : GIL relâché (sinon aucun scaling)

Gates :

* plusieurs TIDs consomment réellement
* %CPU process augmente avec `workers`
* wall diminue de façon monotone

### Option C — Mémoire d’abord (si paging)

Si le gate 1 (mesure propre) échoue :

* prioriser : préallocation buffers, suppression concat, libération intermédiaires, réduction LOD/simplification
* rerun jusqu’à `si/so≈0` et `majflt/s≈0`

---

## Validation finale (preuve de scaling)

* Exécuter 3 runs pour `workers = 1 / 4 / 16 (ou 32)`
* Comparer : wall total, %CPU process moyen, idle machine, `si/so`, `majflt/s`
* Attendu : wall ↓, %CPU ↑, idle ↓, paging ~0.
