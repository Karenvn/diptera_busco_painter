# Examples

This directory contains two small `diptera_odb12` BUSCO examples:

- `idWinCrue1`: `Winthemia cruentata`; Brachycera, so `dbp run --lineage auto`
  selects the Brachycera ALG table.
- `idTipFasc1`: `Tipula fascipennis`; not Brachycera, so `dbp run --lineage auto`
  selects the broader Diptera ALG table.

Each example directory contains:

- `full_table.tsv`: BUSCO input table
- `all_location.tsv`: BUSCO positions with assigned ALGs
- `chrom_lengths.tsv`: final GenBank chromosome lengths
- `summary.tsv`: BUSCO counts per chromosome
- `<ToLID>.png` and `<ToLID>.svg`: chromosome plot

Regenerate both plots from the repository root:

```bash
dbp run \
  --query_table examples/idWinCrue1/full_table.tsv \
  --prefix examples/idWinCrue1/ \
  --lineage auto \
  --accession GCA_965649395.1 \
  --write-summary \
  --label-window-mb 10

dbp run \
  --query_table examples/idTipFasc1/full_table.tsv \
  --prefix examples/idTipFasc1/ \
  --lineage auto \
  --accession GCA_965151645.1 \
  --write-summary \
  --label-window-mb 10
```
