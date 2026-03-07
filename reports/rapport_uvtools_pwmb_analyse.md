# Rapport complet: ouverture et analyse des fichiers PWMB dans UVtools

## 1) Portee et methode

Ce rapport est une analyse **statique du code source** de:

- `/home/kaj/Develop/tools/UVtools`

Objectif: expliquer comment UVtools:

1. ouvre un fichier `.pwmb`,
2. le decode en couches exploitables,
3. lance l'analyse des problemes d'impression.

## 2) Resume executif

- Le format `.pwmb` est gere par la classe `AnycubicFile`.
- L'entree standard passe par `FileFormat.Open(...)`, qui selectionne le parser via l'extension.
- Le decode PWMB lit des tables binaires Anycubic (FileMark/Header/LayerDefinition/etc.), puis decompresse les couches via le codec `PW0` (RLE 4 bits, pas `PWS`).
- L'analyse "qualite d'impression" est executee ensuite par `IssueManager.DetectIssues(...)` (islands, overhangs, resin traps, suction cups, touching bounds, empty layers, print height).

## 3) Pipeline exact d'ouverture d'un `.pwmb`

### 3.1 Resolution du parser

1. `Program.OpenInputFile(...)` appelle `FileFormat.Open(...)`.
   - Reference: `UVtools.Cmd/Program.cs:110-121`
2. `FileFormat.Open(...)` appelle `FindByExtensionOrFilePath(...)`, cree l'instance et lance `Decode(...)`.
   - Reference: `UVtools.Core/FileFormats/FileFormat.cs:741-746`
3. `AnycubicFile` fait partie de la liste globale `AvailableFormats`.
   - Reference: `UVtools.Core/FileFormats/FileFormat.cs:504-513`
4. Dans `AnycubicFile.FileExtensions`, l'extension `pwmb` est declaree explicitement.
   - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:1044-1055`

### 3.2 Identification machine et version

- `pwmb` est mappe vers `AnyCubicMachine.PhotonMonoX6KM3Plus`.
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:1756-1759`
- Les versions "officielles" associees a `pwmb` pour la logique de compatibilite sont `515/516/517`.
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:1176-1180`

## 4) Decode PWMB: fonctionnement interne

### 4.1 Structures et tables lues

Le decode commence par `AnycubicFile.DecodeInternally(...)`.

- Lecture `FileMark` + validations:
  - signature attendue: `ANYCUBIC`
  - verification de version
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:2025-2041`

- Puis lecture conditionnelle des sections:
  - `Header`
  - `Preview` (thumbnail)
  - `LayerImageColorTable` (>= 515)
  - `Extra` + `Machine` (>= 516)
  - `Software` + `Model` (>= 517)
  - `SubLayerDefinition` + `Preview2` (>= 518)
  - References:
    - `UVtools.Core/FileFormats/AnycubicFile.cs:2043-2155`
    - Champs versionnes du `FileMark`: `UVtools.Core/FileFormats/AnycubicFile.cs:156-195`

### 4.2 Chargement des definitions de couches

- `LayersDefinition` est deserialisee, puis `Init(...)` prepare le tableau de layers.
- En mode `Full`, UVtools lit les blocs RLE de chaque couche, puis decode en parallele.
- References: `UVtools.Core/FileFormats/AnycubicFile.cs:2160-2203`

### 4.3 Codec image utilise pour PWMB

- Le choix du codec repose sur `RleFormat`:
  - `.pws` => `PWS`
  - sinon => `PW0`
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:1687-1690`

Pour `.pwmb`, UVtools passe donc par `PW0`:

- `LayerDef.Decode(...)` appelle `DecodePW0(...)` quand le format n'est pas `PWS`.
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:721-724`
- `DecodePW0(...)` decompresse une RLE nibble-based (4 bits) en mat grayscale.
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:2270-2341`

### 4.4 Finalisation apres decode

Apres `DecodeInternally(...)`, `FileFormat.Decode(...)`:

- verifie precision couche,
- sanitise les donnees,
- peut resauvegarder si correction necessaire,
- recalcule bounding rectangle.
- Reference: `UVtools.Core/FileFormats/FileFormat.cs:4634-4684`

## 5) Comment UVtools "analyse" ensuite un PWMB

### 5.1 Point d'entree CLI

Commande CLI: `print-issues`.

- Ouvre le fichier (`Program.OpenInputFile`)
- Construit `IssuesDetectionConfiguration`
- Lance `slicerFile.IssueManager.DetectIssues(...)`
- References:
  - `UVtools.Cmd/Symbols/PrintIssuesCommand.cs:88-105`
  - `UVtools.Cmd/Symbols/PrintIssuesCommand.cs:112-117`

### 5.2 Moteur d'analyse

Dans `IssueManager.DetectIssues(...)`:

- refuse l'analyse si le fichier est en decode partiel (`Partial`).
  - Reference: `UVtools.Core/Managers/IssueManager.cs:121-124`
- utilise un pipeline EmguCV fortement parallele pour la detection geometrique.

### 5.3 Analyse poussee: traitement d'image/contours EmguCV en parallele

#### 5.3.1 Pass principal en parallelisme par couche

- Le coeur de detection geometrique tourne dans `Parallel.For(0, LayerCount, ...)`.
- Chaque iteration travaille sur une couche, avec gestion pause/cancel via `OperationProgress`.
- UVtools saute tres tot les couches vides et les couches non eligibles (whitelist, couche 0, etc.) pour eviter du calcul inutile.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:239-264`

#### 5.3.2 Strategie ROI et reduction de cout memoire/CPU

- Pour minimiser les operations pixel, UVtools travaille sur ROI:
  - ROI de couche courante,
  - union de bounding boxes couche N et N-1 si comparaison inter-couches.
- Les spans (`ReadOnlySpan2D<byte>`) sont utilises pour des acces bas niveau sans surcout d'allocations.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:266-270`
  - `UVtools.Core/Managers/IssueManager.cs:396-401`
  - `UVtools.Core/Managers/IssueManager.cs:495-500`

#### 5.3.3 Overhangs: chaine morphologique + contours

- Pipeline overhang:
  - `Subtract(cur, prev)` pour extraire la matiere "nouvelle",
  - `Threshold(..., Binary)` pour binariser,
  - `Erode` (kernel cross dynamique) pour filtrer artefacts/bruit,
  - `FindContours(Tree)` puis regroupement de contours positifs,
  - filtrage par aire minimale avant creation d'issue.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:401-406`
  - `UVtools.Core/Managers/IssueManager.cs:410-423`

#### 5.3.4 Islands: Connected Components + verification de support reel

- UVtools detecte des composantes connectees (`ConnectedComponentsWithStats`) sur ROI (optionnellement apres threshold).
- Pour chaque composante:
  - extraction rectangle/statistiques,
  - filtrage par aire minimale,
  - comptage pixel-a-pixel des points effectivement supportes sur la couche precedente,
  - decision via ratio `requiredSupportingPixels`.
- Mode "enhanced":
  - croise l'island avec un masque overhang local pour eviter faux positifs.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:454-462`
  - `UVtools.Core/Managers/IssueManager.cs:475-533`
  - `UVtools.Core/Managers/IssueManager.cs:537-585`

#### 5.3.5 Resin-trap/suction-cup: algorithme 2 passes avec carte d'air

- Pass 1 (bas -> haut):
  - generation d'une "air map" (`BitwiseNot` + suppression contours externes),
  - propagation air map couche par couche (`Subtract` + `BitwiseOr`),
  - test de recouvrement contour/air (`BitwiseAnd` + `CountNonZero`) pour classer provisoirement.
- Pass 2 (haut -> bas):
  - reevaluation des contours provisoires avec la connectivite air inverse,
  - bascule resin-trap -> suction-cup si recouvrement air suffisant,
  - maintien de groupes inter-couches par intersection de contours.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:662-713`
  - `UVtools.Core/Managers/IssueManager.cs:715-756`
  - `UVtools.Core/Managers/IssueManager.cs:768-839`
  - `UVtools.Core/Managers/IssueManager.cs:860-933`

#### 5.3.6 Parallelisme interne supplementaire

- En plus du `Parallel.For` principal par couche, UVtools parallelise aussi:
  - le traitement des hollows d'une couche (`Parallel.For`),
  - le dessin des contours air-connectes (`Parallel.ForEach`),
  - la phase d'interpolation/aggregation finale (`Parallel.Invoke`).
- References:
  - `UVtools.Core/Managers/IssueManager.cs:715-756`
  - `UVtools.Core/Managers/IssueManager.cs:801-806`
  - `UVtools.Core/Managers/IssueManager.cs:995-1131`

#### 5.3.7 Gestion de concurrence et hygiene memoire

- Protection des structures partagees par `lock (SlicerFile[layerIndex].Mutex)` lors des ecritures concurrentes.
- Consommation/rotation des matrices via `MatCacheManager` pour limiter les reallocations.
- Liberation explicite de `Mat`/`VectorOfVectorOfPoint` en fin de pipeline.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:730-754`
  - `UVtools.Core/Managers/IssueManager.cs:845-933`
  - `UVtools.Core/Managers/IssueManager.cs:664-673`
  - `UVtools.Core/Managers/IssueManager.cs:1133-1149`

## 6) Reconstitution operationnelle (sequence complete)

1. `FileFormat.Open(path.pwmb)`  
2. selection `AnycubicFile` via extension `.pwmb`  
3. `AnycubicFile.DecodeInternally` lit tables Anycubic  
4. lecture `LayerDefinition` + RLE par couche  
5. decode image couche (PW0) en `Mat`  
6. construction objets `Layer` + metadonnees Z/exposition/mouvements  
7. post-traitement `Decode(...)` global (sanitize, bounding rectangle)  
8. `IssueManager.DetectIssues(...)` pour l'analyse d'impression  

## 7) Commandes utiles pour verifier dans UVtools CLI

Depuis le repo UVtools:

```bash
dotnet run --project UVtools.Cmd -- print-issues /chemin/vers/fichier.pwmb
```

## 8) Points importants / limites observes

- `pwmb` est traite dans `AnycubicFile` avec le profil machine `PhotonMonoX6KM3Plus`.
- Le decode d'analyse exige un `Full decode` (sinon `DetectIssues` retourne vide).
- Le codec utilise pour `.pwmb` suit la branche `PW0` et non `PWS`.
- Le code est concu pour lire des versions Anycubic evolutives (tables conditionnelles par version), avec logique explicite pour >=515/516/517/518.

## 9) Nouvelle analyse ciblee (demandee)

### 9.1 Decodage PWMB (chemin exact)

- Selection du parser:
  - `FileFormat.Open(...)` -> `FindByExtensionOrFilePath(...)` -> instance `AnycubicFile`.
  - References:
    - `UVtools.Core/FileFormats/FileFormat.cs:618-646`
    - `UVtools.Core/FileFormats/FileFormat.cs:741-746`
- Reconnaissance `.pwmb`:
  - extension declaree dans `AnycubicFile.FileExtensions`.
  - machine mappee: `PhotonMonoX6KM3Plus`.
  - References:
    - `UVtools.Core/FileFormats/AnycubicFile.cs:1054-1055`
    - `UVtools.Core/FileFormats/AnycubicFile.cs:1756-1759`
- Decode binaire:
  - lecture `FileMark`, validation signature/version,
  - lecture tables (header, previews, machine/model selon version),
  - lecture `LayerDefinition`,
  - chargement RLE par couche,
  - decode image en parallele.
  - References:
    - `UVtools.Core/FileFormats/AnycubicFile.cs:2027-2041`
    - `UVtools.Core/FileFormats/AnycubicFile.cs:2043-2167`
    - `UVtools.Core/FileFormats/AnycubicFile.cs:2170-2203`

### 9.2 PW0: decompression et "binarization" utile aux overhangs

- Pour `.pwmb`, `RleFormat` retourne `PW0` (tout format non `.pws`).
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:1687-1690`
- `LayerDef.Decode(...)` route donc vers `DecodePW0(...)`.
  - Reference: `UVtools.Core/FileFormats/AnycubicFile.cs:721-724`
- `DecodePW0(...)`:
  - lit chaque octet RLE en nibbles (`code`, `repeat`),
  - reconstruit des niveaux de gris (0, 255, ou niveau 4-bit etendu),
  - remplit le Mat via `FillSpan(...)`,
  - controle strict de bornes (overflow/underflow image).
  - References:
    - `UVtools.Core/FileFormats/AnycubicFile.cs:2270-2341`
    - `UVtools.Core/Extensions/EmguExtensions.cs:488-499`
- Binarisation pour overhang:
  - elle n'est pas faite dans `DecodePW0`, mais plus tard dans le pipeline geometrique:
  - `Subtract(cur, prev)` puis `Threshold(..., 127, 255, Binary)`.
  - References:
    - `UVtools.Core/Managers/IssueManager.cs:401-403`

### 9.3 Overhangs: chaine morphologique + contours + aire

Pipeline observe:

1. extraction de "matiere nouvelle": `CvInvoke.Subtract(image.RoiMat, previousImage.RoiMat, overhangImage)`
2. binarisation: `CvInvoke.Threshold(..., 127, 255, ThresholdType.Binary)`
3. nettoyage morphologique: `CvInvoke.Erode(...)` avec kernel cross dynamique
4. extraction: `FindContours(RetrType.Tree, ChainApproxSimple, offset ROI)`
5. regroupement contours positifs + calcul aire
6. filtrage par aire minimale (`RequiredPixelsToConsider`)

References:

- `UVtools.Core/Managers/IssueManager.cs:401-406`
- `UVtools.Core/Managers/IssueManager.cs:410-417`
- `UVtools.Core/Managers/IssueManager.cs:419-423`

### 9.4 ROI de couche courante (pour limiter cout)

- Le traitement est fait sur la ROI de la couche courante (ou union N/N-1), pas forcement sur l'image complete.
- Cette reduction diminue le nombre de pixels passes dans subtract/threshold/erode/contours.
- Points cle:
  - creation ROI: `layer.GetLayerMat(...)`
  - union inter-couches: `Layer.GetBoundingRectangleUnion(previousLayer, layer)`
  - objet `MatRoi` qui encapsule `SourceMat`, `Roi`, `RoiMat` et leur cycle de vie.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:266`
  - `UVtools.Core/Managers/IssueManager.cs:396`
  - `UVtools.Core/Layers/Layer.cs:1026`
  - `UVtools.Core/EmguCV/MatRoi.cs:27-30`

### 9.5 Spans (acces memoire bas niveau)

- UVtools utilise `ReadOnlySpan2D<byte>` pour lire les pixels sans copies et sans allocations temporaires.
- Exemples:
  - `sourceSpan = image.SourceMat.GetDataByteReadOnlySpan2D()`
  - `roiSpan = image.RoiMat.GetDataByteReadOnlySpan2D()`
  - `previousSpan = previousImage.RoiMat.GetDataByteReadOnlySpan2D()`
- Pour le decode PW0, `FillSpan` saute les runs noirs (cout quasi nul) et n'ecrit que le necessaire.
- References:
  - `UVtools.Core/Managers/IssueManager.cs:268-269`
  - `UVtools.Core/Managers/IssueManager.cs:499`
  - `UVtools.Core/Extensions/EmguExtensions.cs:488-499`

### 9.6 Ce qui est interessant pour multi-core + faible RAM (transposable projet)

Patterns tres utiles observes dans UVtools:

1. Batch + parallelisme borne
   - decode par lots `BatchLayersIndexes(...)` puis `Parallel.ForEach(...)`.
   - evite de saturer memoire en chargeant trop de couches d'un coup.
   - References:
     - `UVtools.Core/FileFormats/FileFormat.cs:3479-3483`
     - `UVtools.Core/FileFormats/AnycubicFile.cs:2170-2188`

2. Reglage global du degre de parallelisme
   - `CoreSettings.MaxDegreeOfParallelism` ajuste le nb de threads.
   - mode "auto-optimal" reserve des coeurs pour la machine.
   - References:
     - `UVtools.Core/CoreSettings.cs:50-64`
     - `UVtools.Core/CoreSettings.cs:77-89`

3. Cache de Mats fenetre glissante
   - `MatCacheManager` precharge une fenetre, puis `Consume(...)` pour liberer immediatement.
   - utile pour algorithmes multi-passes (resin-trap) sans garder tout en RAM.
   - References:
     - `UVtools.Core/Managers/MatCacheManager.cs:107-114`
     - `UVtools.Core/Managers/MatCacheManager.cs:163-170`
     - `UVtools.Core/Managers/MatCacheManager.cs:271-280`

4. Auto-dispose explicite
   - usage intensif de `using` + `Dispose()` sur `Mat`/contours.
   - limite fortement les pics memoire natifs OpenCV.
   - References:
     - `UVtools.Core/Managers/IssueManager.cs:592-594`
     - `UVtools.Core/Managers/IssueManager.cs:1133-1149`

5. Evitement de calculs inutiles
   - skip precoce couche vide / hors whitelist / non eligibles.
   - supprime beaucoup de travail CPU sur gros jobs.
   - References:
     - `UVtools.Core/Managers/IssueManager.cs:249-264`

### 9.7 Gestion du cache des layers binarizes

Objectif du design UVtools: ne pas binariser/recharger toutes les couches en memoire en meme temps.

- Le cache est centralise dans `MatCacheManager`:
  - fenetre glissante de couches (`CacheCount`),
  - plusieurs representations par couche possibles (`ElementsPerCache`),
  - references:
    - `UVtools.Core/Managers/MatCacheManager.cs:29-35`
    - `UVtools.Core/Managers/MatCacheManager.cs:105-114`

- Construction d'un layer binaire en cache:
  - voie generique: `StripAntiAliasing=true` applique un `Threshold(127)` directement pendant le prechargement.
  - voie personnalisee: `AfterCacheAction` permet de construire un element derive (ex: ROI + seuillage specifique).
  - references:
    - `UVtools.Core/Managers/MatCacheManager.cs:64`
    - `UVtools.Core/Managers/MatCacheManager.cs:181-186`
    - `UVtools.Core/Managers/MatCacheManager.cs:94`

- Cas concret dans `IssueManager` (resin-trap):
  - `MatCacheManager(SlicerFile, 0, 2)` => 2 mats par couche:
    - `mats[0]`: couche source,
    - `mats[1]`: ROI binarisee (`BoundingRectangle` + threshold `MaximumPixelBrightnessToDrain`).
  - le traitement consomme ensuite `matCache.Get(layerIndex, 1)` pour utiliser la version binarisee.
  - references:
    - `UVtools.Core/Managers/IssueManager.cs:664-671`
    - `UVtools.Core/Managers/IssueManager.cs:683`

- Controle memoire:
  - liberation immediate par couche via `Consume(layerIndex)`,
  - purge selective via `ClearButKeep(...)`,
  - destruction complete via `Dispose()` -> `Clear()`.
  - references:
    - `UVtools.Core/Managers/MatCacheManager.cs:271-280`
    - `UVtools.Core/Managers/MatCacheManager.cs:287-297`
    - `UVtools.Core/Managers/MatCacheManager.cs:302-314`

- Benefice pratique pour votre projet:
  - garder un pipeline "decode gris -> derive binaire en cache -> calcul -> consume"
  - eviter les buffers globaux de toutes les couches,
  - conserver uniquement une fenetre locale (N couches) adaptee au nombre de coeurs et a la RAM dispo.
