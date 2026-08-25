# FCP AutoCut

Prototype du moteur d'une future Workflow Extension Final Cut Pro. Il détecte les
silences audio et produit les plages temporelles à retirer. Le projet original
Final Cut Pro n'est jamais modifié.

## Périmètre du MVP

- seuil audio réglable (défaut : `-40 dB`) ;
- silence strictement supérieur à 2 secondes ;
- marge conservée autour de la parole (défaut : `200 ms`) ;
- rapport lisible ou JSON ;
- génération d'un nouveau projet FCPXML pour une vidéo source unique ;
- analyse locale avec FFmpeg.

L'interface intégrée à Final Cut Pro constituera l'étape suivante. Le SDK
Workflow Extension d'Apple nécessite macOS, Xcode et Final Cut Pro.

## Utilisation

Pré-requis : Python 3.11+, `ffmpeg` et `ffprobe` dans le `PATH`. Installer d'abord
la commande depuis une copie locale du dépôt :

```bash
python3 -m pip install -e .
fcp-autocut interview.mov

# Réglages personnalisés et sortie exploitable par une interface
fcp-autocut interview.mov \
  --threshold-db -35 \
  --minimum-silence 2.5 \
  --padding 0.15 \
  --json > plan.json

# Crée un projet à importer dans Final Cut Pro
fcp-autocut interview.mov --fcpxml "Interview — AutoCut.fcpxml"
```

Le FCPXML généré référence le média original sans le réencoder. Dans Final Cut
Pro, utiliser **Fichier > Importer > XML**, puis choisir le fichier produit.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Les tests comprennent une analyse audio réelle : ils génèrent un fichier WAV
temporaire (1 s de son, 3 s de silence, 1 s de son) et l'analysent avec FFmpeg.
