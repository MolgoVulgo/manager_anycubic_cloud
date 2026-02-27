## Résumé — récupérer les metrics pendant un run (PID connu)

Hypothèse : `pid=<PID_DU_PYTHON>` (remplace).

### Prérequis (pour que les métriques soient complètes)
- `perf` : profiling CPU (hotspots)
- `pidstat` : RSS / page faults / CPU process

Sur Arch :
```bash
sudo pacman -S sysstat
sudo pacman -S perf || sudo pacman -S linux-tools
```

Optionnel (uniquement si tu veux interroger OpenCV **via Python**):
- `cv2` = bindings Python d’OpenCV (`opencv-python` ou paquet distro).
- Ne pas confondre : `opencv2` = headers C++ ; `cv2` = module Python.

---

### 1) Affinité CPU + nombre de threads
```bash
pid=<PID_DU_PYTHON>
taskset -pc $pid
cat /proc/$pid/status | egrep 'Cpus_allowed_list|Threads'
ls /proc/$pid/task | wc -l
```

---

### 2) Threads réellement actifs (sur quels cœurs, combien consomment)
```bash
pid=<PID_DU_PYTHON>
ps -L -p $pid -o pid,tid,psr,pcpu,comm --sort=-pcpu | head -n 30
# fallback si ps est “aveugle” sur ton env:
top -H -p $pid
```

---

### 3) Profil “où part le CPU” (GIL/libpython vs module natif)
```bash
pid=<PID_DU_PYTHON>
sudo perf top -p $pid
```

---

### 4) Pression mémoire / swap (paging)
```bash
vmstat 1
```

Et mémoire du process (RSS, faults) :
```bash
pid=<PID_DU_PYTHON>
pidstat -r -u -p $pid 1
```

---

### 5) Vérifier si le module natif est threadé (OpenMP/TBB) + libs liées
1) Localiser le `.so` :
```bash
python - <<'PY'
import pwmb_geom
print(pwmb_geom.__file__)
import pwmb_geom._pwmb_geom as m
print(m.__file__)
PY
```

2) Vérifier les libs (OpenMP/TBB/pthreads) :
```bash
ldd /chemin/vers/_pwmb_geom*.so | egrep 'gomp|omp|tbb|pthread'
```

---

### 6) Variables d’environnement qui brident le parallélisme
```bash
env | egrep 'OMP|OPENBLAS|MKL|NUMEXPR|TBB|OPENCV|KMP|GOMP'
```

---

### 7) (Optionnel) OpenCV côté Python : threads/cpus
```bash
python - <<'PY'
import cv2
print("opencv threads:", cv2.getNumThreads())
print("opencv cpus:", cv2.getNumberOfCPUs())
PY
```
Si `ModuleNotFoundError: No module named 'cv2'` : bindings Python non installés (ça ne bloque pas la voie C++).

---

### 8) Collecte post-run (campagne) : rapports + extraction rapide
```bash
# lancer la campagne
bash tools/run_campaign_z1_xy1.sh pwmb_files reports

# lister les artefacts
ls -lh reports/render3d_campaign_*_z1_xy1.*

# extraire wall/cpu des JSON (si jq installé)
jq '.runs[] | {name, total_wall_ms, total_cpu_s, workers_effective, layer_count, triangle_vertices_count}'   reports/render3d_campaign_summary_z1_xy1.json
```

---

## Mesures réelles — Campagne complète relancée (2026-02-26)
## Mesures réelles — Campagne complète relancée (2026-02-26)

Commande de campagne exécutée:

```bash
bash tools/run_campaign_z1_xy1.sh pwmb_files reports
```

Statut:
- campagne complète terminée (`step 1/3 native`, `step 2/3 opencv`, `step 3/3 summary`).
- rapports générés:
  - `reports/render3d_campaign_cpp_native_z1_xy1.json`
  - `reports/render3d_campaign_cpp_opencv_z1_xy1.json`
  - `reports/render3d_campaign_summary_z1_xy1.json`
  - `reports/render3d_campaign_summary_z1_xy1.md`

### Snapshot pendant `cpp native` (pid=80498)

```text
timestamp: 2026-02-26T14:13:32+01:00
pid: 80498
== 1) Affinité CPU + nombre de threads ==
pid 80498's current affinity list: 0-31
Threads:	33
Cpus_allowed_list:	0-31
task_count: 33

== 2) Threads actifs ==
    PID     TID PSR %CPU COMMAND
  80498   80498  23  169 python

== 3) perf top (tentative) ==
timeout: failed to run command ‘perf’: No such file or directory

== 4) vmstat (3s) ==
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 2  0 3921224 20207828 93060 3193732 95  85  2306   766 32282  15  6  1 93  0  0  0
 1  0 3921212 20352864 93068 3196400 0    0   576  1584 49860 91484 5 1 94  0  0  0
 1  0 3921204 20242456 93068 3201692 0    0     0     0 27773 42460 4 1 95  0  0  0

== 4bis) pidstat (3s) ==
zsh:20: command not found: pidstat

== 6) env caps ==
CSF_EXCEPTION_PROMPT=1
```

### Snapshot pendant `cpp opencv` (pid=85147)

```text
timestamp: 2026-02-26T14:29:57+01:00
pid: 85147
== 1) Affinité CPU + nombre de threads ==
pid 85147's current affinity list: 0-31
Threads:	64
Cpus_allowed_list:	0-31
task_count: 64

== 2) Threads actifs ==
    PID     TID PSR %CPU COMMAND
  85147   85147   3  310 python

== 3) perf top (tentative) ==
timeout: failed to run command ‘perf’: No such file or directory

== 4) vmstat (3s) ==
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 1  0 5412380 25243060 17472 865596 90   94  2198   761 32212  15  6  1 93  0  0  0
 3  0 5412276 25181252 17472 864436  0    0  1764     0 68611 140277 5 2 94 0  0  0
 1  0 5412148 25204672 17472 866640  0    0  1228     0 77183 152842 5 2 94 0  0  0

== 4bis) pidstat (3s) ==
zsh:20: command not found: pidstat

== 6) env caps ==
CSF_EXCEPTION_PROMPT=1
```

### Module natif et libs liées

```text
pwmb_geom.__file__:
/home/kaj/Develop/python/manager_anycubic_cloud/pwmb_geom/__init__.py

pwmb_geom._pwmb_geom module file:
/home/kaj/Develop/python/manager_anycubic_cloud/pwmb_geom/_pwmb_geom.cpython-314-x86_64-linux-gnu.so

ldd (_pwmb_geom) filtered (gomp|omp|tbb|pthread):
libtbb.so.12 => /usr/lib/libtbb.so.12 (0x00007f9998bac000)
```

### Environnement parallélisme + OpenCV Python

```text
env | egrep 'OMP|OPENBLAS|MKL|NUMEXPR|TBB|OPENCV|KMP|GOMP':
CSF_EXCEPTION_PROMPT=1

python - <<'PY'
import cv2
print('opencv threads:', cv2.getNumThreads())
print('opencv cpus:', cv2.getNumberOfCPUs())
PY

Résultat:
ModuleNotFoundError: No module named 'cv2'
```

---

## Lecture rapide des captures (ce que ça permet de conclure)
- `workers_effective` dans le summary = capacité/config ; ça ne prouve pas l’occupation CPU réelle.
- Snapshots : un seul thread “dominant” (python ~170–310% CPU) + CPU global très idle (~93–96%) ⇒ hotpath majoritairement série **ou** blocage mémoire/I/O.
- `swpd` non nul + `si/so` visibles au début des captures ⇒ swap en jeu : peut tuer le scaling même avec des threads.
- `_pwmb_geom` lié à `libtbb` ⇒ tu as une brique de parallélisme native disponible, mais pas garanti que le chemin chaud l’exploite.
- `perf` et `pidstat` absents pendant ces runs ⇒ impossible de trancher proprement entre : GIL, C++ sériel, ou copies/allocs.

### Prochaine itération (diagnostic non-ambigu)
Pendant un run :
1) `sudo perf top -p $pid` (hotspot exact)
2) `pidstat -r -u -p $pid 1` + `vmstat 1` (RSS/faults vs swap)

Ensuite seulement : décisions (release GIL autour du compute natif, paralléliser côté TBB/OpenMP, ou réduire copies mémoire via préallocation/LOD).

---

## Mesures réelles — Campagne complète relancée (2026-02-26, rerun après MAJ du fichier)

Commande de campagne exécutée:

```bash
bash tools/run_campaign_z1_xy1.sh pwmb_files reports
```

Statut:
- campagne complète terminée (`step 1/3 native`, `step 2/3 opencv`, `step 3/3 summary`).
- rapports mis à jour:
  - `reports/render3d_campaign_cpp_native_z1_xy1.json` (2026-02-26 16:47)
  - `reports/render3d_campaign_cpp_opencv_z1_xy1.json` (2026-02-26 17:06)
  - `reports/render3d_campaign_summary_z1_xy1.json` (2026-02-26 17:06)
  - `reports/render3d_campaign_summary_z1_xy1.md` (2026-02-26 17:06)

### Snapshot pendant `cpp native` (pid=651973)

```text
# native rerun snapshot
2026-02-26T16:26:51+01:00
pid=651973

## Affinité / cpuset / threads réels
pid 651973's current affinity list: 0-31
Threads:	33
Cpus_allowed_list:	0-31
    PID     TID PSR %CPU COMMAND
 651973  651973   3  195 python

## perf top (tentative)
Error: Access to performance monitoring and observability operations is limited.
perf_event_paranoid setting is 2

## vmstat (3s)
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
16  0 5271608 13915664 209376 7236904 69 99  2000   719 28412  13  5  1 94  0  0  0
 5  0 5271220 13792940 209388 7246516 0   0 10120  1820 123009 231818 14 4 81 0 0 0
 4  0 5270844 13790904 209388 7254816 0   0  4992     4 97990 151173 14 4 83 0 0  0

## pidstat (3s) moyenne
Average: %CPU=117.33, minflt/s=20597.33, majflt/s=2.00, RSS=1966052 KB, %MEM=6.00

## module natif + libs
pwmb_geom.__file__: /home/kaj/Develop/python/manager_anycubic_cloud/pwmb_geom/__init__.py
pwmb_geom._pwmb_geom.__file__: /home/kaj/Develop/python/manager_anycubic_cloud/pwmb_geom/_pwmb_geom.cpython-314-x86_64-linux-gnu.so
libtbb.so.12 => /usr/lib/libtbb.so.12

## Environnement / OpenCV
CSF_EXCEPTION_PROMPT=1
opencv threads: 32
opencv cpus: 32
```

### Snapshot pendant `cpp opencv` (pid=660473)

```text
# opencv rerun snapshot
2026-02-26T16:48:17+01:00
pid=660473

## Affinité / cpuset / threads réels
pid 660473's current affinity list: 0-31
Threads:	64
Cpus_allowed_list:	0-31
    PID     TID PSR %CPU COMMAND
 660473  660473  24  224 python

## perf top (tentative)
Error: Access to performance monitoring and observability operations is limited.
perf_event_paranoid setting is 2

## vmstat (3s)
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 2  0 11784988 19167860 34388 2010692 67 130 2215   728 35543  16  7  1 92  0  0  0
 2  0 11784968 19112276 34396 2011296 4   0   388   144 86692 153128 12 3 85 0 0  0
 6  0 11784840 19236212 34396 2013228 64  0  1988     0 96327 177350 13 3 84 0 0  0

## pidstat (3s) moyenne
Average: %CPU=163.00, minflt/s=9961.33, majflt/s=2.00, RSS=2781479 KB, %MEM=8.49

## Environnement / OpenCV
CSF_EXCEPTION_PROMPT=1
opencv threads: 32
opencv cpus: 32
```

### Résumé campagne (`reports/render3d_campaign_summary_z1_xy1.md`)

```text
workers_effective:
- cpp_native: 32
- cpp_opencv: 32

aggregate wall (ms):
- cpp_native total_wall_ms: 1199343.947
- cpp_opencv total_wall_ms: 1074465.720
- cpp_native contours_wall_ms_total: 431935.202
- cpp_opencv contours_wall_ms_total: 320762.339
- cpp_native triangulation_wall_ms_total: 764120.442
- cpp_opencv triangulation_wall_ms_total: 749774.701

aggregate cpu cumulée (ms):
- cpp_native total_cpu_ms: 27456614.436
- cpp_opencv total_cpu_ms: 23126513.793

speedup (native vs opencv):
- cpp_native_vs_opencv_total_x: 0.8959
- cpp_native_vs_opencv_total_cpu_x: 0.8423
- cpp_native_vs_opencv_contours_x: 0.7082
- cpp_native_vs_opencv_triangulation_x: 0.9371
```

### Conclusion de ce rerun
- Sur ce passage précis, `opencv` est plus rapide que `native` en wall et en CPU cumulé.
- Le parallélisme est bien configuré au max (32 workers effectifs, affinité `0-31`).
- Les snapshots restent compatibles avec un chemin de calcul encore partiellement sériel (un thread dominant visible dans `ps -L`) et une pression mémoire/swap non nulle.
