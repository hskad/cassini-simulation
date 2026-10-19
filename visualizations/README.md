# Saved figures

| Folder | Purpose |
| --- | --- |
| `readme/` | Current plots, animations, and their source manifest. The main README uses these files. |
| `archive/` | Original plots and animations from the previous runtime model. |

Rebuild the current figures from the project root:

```bash
python3 cassini.py docs
```

Keep the archive for reference to the original visual style. Its speedup values
are not validated results from the current simulator. The build command does
not change the archive.

Save new experiment plots under `output/<run>/plots/`. Do not add run results
to this folder.
