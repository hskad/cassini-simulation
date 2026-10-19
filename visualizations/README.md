# Saved figures

| Folder | Purpose |
| --- | --- |
| `readme/` | Current plots, animations, and their source manifest. The main README uses these files. |

Rebuild the current figures from the project root:

```bash
python3 cassini.py docs
```

The current figures retain the original visual style. Old figures from the
previous runtime model are available in Git history. Their speedup values are
not validated results from the current simulator.

Save new experiment plots under `output/<run>/plots/`. Do not add run results
to this folder.
