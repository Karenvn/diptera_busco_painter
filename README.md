# diptera-busco-painter

Utilities for plotting BUSCO `full_table.tsv` rows as Diptera ancestral linkage
group (ALG) assignments across chromosomes or scaffolds for genome notes.

This repository is adapted from `/Users/kh18/code/merian-busco-painter`, but uses
the Diptera ALG tables from `Obscuromics/diptera-ALGs` instead of Merian element
tables.

Gries *et al.* (2026) reconstructed six Diptera ancestral linkage groups
(ALGs) from chromosome-level genome assemblies. These six ALGs are conserved in
many Nematoceran lineages, while the emergence of Brachycera coincided with four
chromosomal fissions. This is why the package includes both a broad Diptera ALG
table and a Brachycera-specific ALG table. doi:
[10.64898/2026.06.01.729285](https://doi.org/10.64898/2026.06.01.729285)

## BUSCO version

The included ALG tables are expected to be used with BUSCO `diptera_odb12`.
The mapper checks the BUSCO header and warns when the input table reports a
different lineage dataset, such as `diptera_odb10`.


## Bundled ALG reference tables

- Diptera: `src/diptera_busco_painter/data/ALGs_syngraph_diptera.tsv`
- Brachycera: `src/diptera_busco_painter/data/ALGs_syngraph_brachycera.tsv`

Original sources:

- <https://raw.githubusercontent.com/Obscuromics/diptera-ALGs/refs/heads/main/tables/ALGs_syngraph_diptera.tsv>
- <https://raw.githubusercontent.com/Obscuromics/diptera-ALGs/refs/heads/main/tables/ALGs_syngraph_brachycera.tsv>

## Install

```bash
cd /Users/kh18/code/diptera_busco_painter
python3 -m pip install -e .
```

Installed commands:

```bash
diptera-busco-painter --help
dbp --help
dbp run --help
buscopainter --help
plot-buscopainter --help
```

## Lineage selection

The `run` and `paint` steps accept:

- `--lineage diptera`
- `--lineage brachycera`
- `--lineage auto`

`--lineage auto` selects Brachycera if it can prove Brachycera membership from
one of:

- `--taxon-lineage "Diptera; Brachycera; ..."`
- `--taxid`
- `--accession`, using the NCBI Datasets API

If auto cannot resolve Brachycera membership, it falls back to the broader
Diptera table and prints a warning.

## Local Examples

Use this pattern once the BUSCO table has been rerun with `diptera_odb12`.
`--accession` lets `dbp run` choose the correct ALG table and write public
GenBank chromosome accessions for final plotting.

`idWinCrue1` is Brachycera, so auto selection uses the Brachycera ALG table:

```bash
cd /Users/kh18/code/diptera_busco_painter

dbp run \
  --query_table examples/idWinCrue1/full_table.tsv \
  --prefix examples/idWinCrue1/ \
  --lineage auto \
  --accession GCA_965649395.1 \
  --write-summary \
  --label-window-mb 10
```

`idTipFasc1` is *Tipula*, not Brachycera, so auto selection uses the broader
Diptera ALG table:

```bash
dbp run \
  --query_table examples/idTipFasc1/full_table.tsv \
  --prefix examples/idTipFasc1/ \
  --lineage auto \
  --accession GCA_965151645.1 \
  --write-summary \
  --label-window-mb 10
```

In this mode, `dbp run` writes GenBank accessions in `chrom_lengths.tsv`.
If the BUSCO table uses assembly sequence names such as `SUPER_1`, those names
are remapped to their matching GenBank accessions in `all_location.tsv` before
plotting, so the final plot labels remain the public GenBank chromosome
accessions.

## Outputs

`dbp run` writes the final plot and the intermediate audit tables:

- `all_location.tsv`
- `chrom_lengths.tsv` when `--accession` is used
- `summary.tsv` when `--write-summary` is used
- `<prefix>.png`
- `<prefix>.svg`

`all_location.tsv` columns:

- `buscoID`
- `query_chr`
- `position`
- `assigned_alg`
- `status`

The lower-level `dbp paint` command writes the same intermediate tables.
The lower-level `dbp plot` command writes:

- `<prefix>.png`
- `<prefix>.svg`

The plotter accepts either:

- `chrom_lengths.tsv` from `dbp run --accession` or `dbp paint --accession`
  with `--assembly-mode final`
- a local `.fai` index with `--assembly-mode draft`

If no lengths file is supplied, lengths are estimated from BUSCO positions.
When a lengths file is supplied, all chromosomes/scaffolds in that file are
plotted, including BUSCO-less or ALG-less ones.

## Shorter ALG Labels

By default, chromosome labels list every ALG with at least `--label-threshold`
BUSCOs on that chromosome. To show only the dominant ALG in genomic windows, use
`--label-window-mb`.

Example:

```bash
dbp run \
  --query_table examples/idWinCrue1/full_table.tsv \
  --prefix examples/idWinCrue1/ \
  --lineage auto \
  --accession GCA_965649395.1 \
  --write-summary \
  --label-window-mb 20 \
  --label-window-min-buscos 5 \
  --label-window-min-fraction 0.5
```

Larger windows and higher `--label-window-min-fraction` values produce shorter,
more conservative label lists. `--label-window-mb 0` keeps the default
chromosome-wide labels. If you only want to change label settings after a run,
use `dbp plot` on the existing `all_location.tsv`.

## Palette

The plotting palette is:

| ALG | Colour |
| --- | --- |
| d1 | `#169e73ff` |
| d2 | `#e59d38ff` |
| d3 | `#1573afff` |
| d4 | `#f0e354ff` |
| d5 | `#60b5e1ff` |
| d6 | `black` |
| db1a | `#25d8a0ff` |
| db1b | `#168a65ff` |
| db2a | `#fccf8f` |
| db2b | `#f29717ff` |
| db3a | `#8d96e5` |
| db3b | `#005990ff` |
| db4a | `#f0e354ff` |
| db4b | `#e2d119ff` |
| db5 | `#60b5e1ff` |
| db6 | `black` |


## Batch workflow

The wrapper expects BUSCO results at:

```text
${BUSCO_DIR}/${ToLID}/full_table.tsv
```

It also needs a tab-separated accession table with at least:

```text
ToLID<TAB>assembly_accession
```

The table may have extra columns, such as species name. The canonical filename
is:

- `tolid_accessions.tsv`

If `ACCESSION_FILE` is not set, the wrapper searches the working directory and
this repository for `tolid_accessions.tsv`. It also accepts these legacy aliases:

- `tolid_accession.tsv`
- `tolids_accession.tsv`
- `tolids_accessions.tsv`

With the default `LINEAGE=auto`, the wrapper passes each assembly accession to
`dbp run`; `dbp run` looks up the NCBI taxid for that accession and selects
the Brachycera ALG table when the taxonomic lineage contains Brachycera.
Otherwise it uses the broader Diptera table.

Run:

```bash
bash busco_to_diptera_algs.sh
```

Environment variables:

```bash
DATA_ROOT=/path/to/project_data
BUSCO_DIR=/path/to/project_data/busco
OUTPUT_DIR=/path/to/project_data/diptera_algs
ACCESSION_FILE=/Users/kh18/code/diptera_busco_painter/tolid_accessions.tsv
LINEAGE=auto
LABEL_WINDOW_MB=10
LABEL_WINDOW_MIN_FRACTION=0.5
bash busco_to_diptera_algs.sh
```

Set `ALG_REF=/path/to/custom.tsv` only when you want to override the bundled
Diptera/Brachycera tables.
