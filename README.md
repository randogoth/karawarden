Repository moved to [codeberg.org/randogoth/karawarden.git](https://codeberg.org/randogoth/karawarden.git)

## Migrate Hoarder/Karakeep to Linkwarden

Small helper that reshapes a Hoarder/Karakeep export into something Linkwarden’s importer accepts.

### Usage

```bash
python3 convert.py hoarder-export.json --output linkwarden-import.json
```

- The script puts every link into a single `Hoarder Import` collection.
- Tags are copied exactly as they appear in the export.
- Optional flags: `--user-id` (defaults to `1`) and `--collection-color`.