"""Map BUSCO full_table rows to Diptera ancestral linkage groups."""

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import requests

API_KEY = os.getenv("NCBI_API_KEY")
EXPECTED_BUSCO_LINEAGE = "diptera_odb12"
DIPTERA_TAXID = 7147
BRACHYCERA_TAXID = 7203
LINEAGE_CHOICES = ("auto", "diptera", "brachycera")
BUNDLED_ALG_TABLES = {
    "diptera": "data/ALGs_syngraph_diptera.tsv",
    "brachycera": "data/ALGs_syngraph_brachycera.tsv",
}
VALID_ALG_LABELS = {
    "d1",
    "d2",
    "d3",
    "d4",
    "d5",
    "d6",
    "db1a",
    "db1b",
    "db2a",
    "db2b",
    "db3a",
    "db3b",
    "db4a",
    "db4b",
    "db5",
    "db6",
}


@dataclass(frozen=True)
class PaintOutputs:
    all_locations: Path
    chrom_lengths: Path
    summary: Path
    wrote_lengths: bool
    wrote_summary: bool
    lineage: str
    reference_table: Path
    busco_dataset: str | None
    mapped_buscos: int
    total_buscos: int


def bundled_reference_table(lineage: str) -> Path:
    if lineage not in BUNDLED_ALG_TABLES:
        raise ValueError(f"Unknown bundled ALG lineage: {lineage}")
    ref = files("diptera_busco_painter").joinpath(BUNDLED_ALG_TABLES[lineage])
    return Path(str(ref))


def parse_busco_dataset(path: Path) -> str | None:
    """Return the BUSCO lineage dataset named in a full_table.tsv header."""
    marker = "# The lineage dataset is:"
    with path.open() as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            if line.startswith(marker):
                return line.removeprefix(marker).strip().split()[0]
    return None


def parse_busco_table(path: Path) -> tuple[list[tuple[str, str, int, int]], list[str]]:
    """Return BUSCO ID, chromosome, start and stop for Complete/Duplicated rows."""
    table: list[tuple[str, str, int, int]] = []
    chromosomes: set[str] = set()
    keep_status = {"Complete", "Duplicated"}

    with path.open(newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#") or len(row) < 5:
                continue
            busco_id, status, chrom, start, stop = row[:5]
            if status not in keep_status:
                continue
            try:
                start_coord, end_coord = int(start), int(stop)
            except ValueError:
                continue
            table.append((busco_id, chrom, start_coord, end_coord))
            chromosomes.add(chrom)
    return table, sorted(chromosomes)


def build_ref_map(ref_path: Path) -> dict[str, str]:
    """Return BUSCO ID to Diptera ALG mapping from a two-column ALG table."""
    ref_map: dict[str, str] = {}
    with ref_path.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            row = line.split()
            if len(row) < 2 or row[0].lower() == "busco":
                continue
            alg = row[1].lower().strip()
            if alg in VALID_ALG_LABELS:
                ref_map[row[0]] = alg
    return ref_map


def build_location_rows(
    ref_map: dict[str, str], query_table: list[tuple[str, str, int, int]]
) -> tuple[list[str], int]:
    rows = ["buscoID\tquery_chr\tposition\tassigned_alg\tstatus"]
    mapped = 0
    for busco_id, query_chr, start, end in query_table:
        position = (start + end) / 2
        assigned = ref_map.get(busco_id, "NA")
        status = "assigned" if assigned != "NA" else "unassigned"
        if assigned != "NA":
            mapped += 1
        rows.append(f"{busco_id}\t{query_chr}\t{position}\t{assigned}\t{status}")
    return rows, mapped


def ncbi_json(url: str) -> dict:
    headers = {"accept": "application/json", "User-Agent": "diptera-busco-painter"}
    params = {}
    if API_KEY:
        params["api_key"] = API_KEY
    response = requests.get(url, headers=headers, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_assembly_taxid(accession: str) -> int | None:
    url = (
        "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/"
        f"{accession}/dataset_report"
    )
    payload = ncbi_json(url)
    reports = payload.get("reports", [])
    if not reports:
        return None
    tax_id = reports[0].get("organism", {}).get("tax_id")
    return int(tax_id) if tax_id else None


def fetch_taxonomy_lineage_ids(taxid: int) -> set[int]:
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{taxid}"
    payload = ncbi_json(url)
    nodes = payload.get("taxonomy_nodes", [])
    if not nodes:
        return {taxid}
    taxonomy = nodes[0].get("taxonomy", {})
    lineage = {int(item) for item in taxonomy.get("lineage", [])}
    lineage.add(int(taxonomy.get("tax_id", taxid)))
    return lineage


def lineage_from_taxonomy_ids(lineage_ids: set[int]) -> str | None:
    if BRACHYCERA_TAXID in lineage_ids:
        return "brachycera"
    if DIPTERA_TAXID in lineage_ids:
        return "diptera"
    return None


def choose_reference_lineage(
    lineage: str,
    taxid: int | None = None,
    taxon_lineage: str | None = None,
    accession: str | None = None,
) -> str:
    """Resolve the bundled ALG table to use."""
    if lineage not in LINEAGE_CHOICES:
        raise ValueError(f"Unknown lineage: {lineage}")
    if lineage != "auto":
        return lineage

    if taxon_lineage:
        lower_lineage = taxon_lineage.lower()
        if "brachycera" in lower_lineage:
            print("[INFO] Auto lineage selected Brachycera from taxonomy text")
            return "brachycera"
        if "diptera" in lower_lineage:
            print("[INFO] Auto lineage selected Diptera from taxonomy text")
            return "diptera"

    if taxid is not None:
        try:
            selected = lineage_from_taxonomy_ids(fetch_taxonomy_lineage_ids(taxid))
            if selected:
                print(f"[INFO] Auto lineage selected {selected} from taxid {taxid}")
                return selected
        except requests.RequestException as exc:
            print(f"[WARN] Could not fetch NCBI taxonomy for taxid {taxid}: {exc}")

    if accession:
        try:
            assembly_taxid = fetch_assembly_taxid(accession)
            if assembly_taxid is not None:
                selected = lineage_from_taxonomy_ids(
                    fetch_taxonomy_lineage_ids(assembly_taxid)
                )
                if selected:
                    print(
                        "[INFO] Auto lineage selected "
                        f"{selected} from accession {accession} "
                        f"(taxid {assembly_taxid})"
                    )
                    return selected
        except requests.RequestException as exc:
            print(f"[WARN] Could not fetch NCBI taxonomy for {accession}: {exc}")

    print("[WARN] Could not resolve Brachycera membership; using Diptera ALG table")
    return "diptera"


def fetch_sequence_report(accession: str) -> list[dict]:
    url = (
        "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/"
        f"{accession}/sequence_reports"
    )
    print(f"[INFO] Fetching chromosome info from NCBI for {accession}...")
    payload = ncbi_json(url)
    return payload.get("sequence_report", {}).get("records") or payload.get(
        "reports", []
    )


def sequence_name_to_genbank_map(records: list[dict]) -> dict[str, str]:
    """Map NCBI sequence names and accessions to GenBank accessions."""
    chrom_map: dict[str, str] = {}
    for rec in records:
        genbank = rec.get("genbank_accession")
        if not genbank:
            continue
        for field in ("genbank_accession", "refseq_accession", "sequence_name"):
            value = rec.get(field)
            if value:
                chrom_map[value] = genbank
    return chrom_map


def remap_query_chromosomes(
    query_rows: list[tuple[str, str, int, int]], chrom_map: dict[str, str]
) -> tuple[list[tuple[str, str, int, int]], int]:
    """Return query rows with sequence IDs converted to GenBank accessions."""
    remapped: list[tuple[str, str, int, int]] = []
    changed = 0
    for busco_id, query_chr, start, end in query_rows:
        mapped_chr = chrom_map.get(query_chr, query_chr)
        if mapped_chr != query_chr:
            changed += 1
        remapped.append((busco_id, mapped_chr, start, end))
    return remapped, changed


def chrom_lengths_with_unloc(records: list[dict]) -> list[tuple[str, int]]:
    """Return main GenBank chromosome accession and bp length including unlocalized scaffolds."""
    print("[INFO] Using NCBI GenBank accessions for chromosome labels")
    main_acc: dict[str, str] = {}
    for rec in records:
        if (
            rec.get("role") == "assembled-molecule"
            and rec.get("assigned_molecule_location_type") == "Chromosome"
        ):
            genbank = rec.get("genbank_accession")
            if genbank:
                main_acc[rec["chr_name"]] = genbank

    bp_tot: dict[str, int] = {acc: 0 for acc in main_acc.values()}
    for rec in records:
        role = rec.get("role")
        loc = rec.get("assigned_molecule_location_type", "")
        if role == "assembled-molecule" and loc == "Chromosome":
            acc = rec.get("genbank_accession")
            if acc in bp_tot:
                bp_tot[acc] += int(rec.get("length", 0))
        elif role == "unlocalized-scaffold":
            parent = rec.get("chr_name")
            acc = main_acc.get(parent)
            if acc:
                bp_tot[acc] += int(rec.get("length", 0))

    return sorted(bp_tot.items(), key=lambda item: -item[1])


def write_tsv(lines: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def resolve_output_paths(prefix: str | Path) -> tuple[Path, Path, Path]:
    """Resolve output paths from either a directory-like prefix or file stem."""
    prefix_text = str(prefix)
    prefix_path = Path(prefix)
    if prefix_text.endswith(("/", "\\")) or prefix_path.is_dir():
        out_dir = prefix_path
        return (
            out_dir / "all_location.tsv",
            out_dir / "chrom_lengths.tsv",
            out_dir / "summary.tsv",
        )

    out_dir = prefix_path.parent
    stem = prefix_path.name
    return (
        out_dir / f"{stem}_all_location.tsv",
        out_dir / f"{stem}_chrom_lengths.tsv",
        out_dir / f"{stem}_summary.tsv",
    )


def paint_buscos(
    query_table: Path,
    prefix: str | Path,
    reference_table: Path | None = None,
    lineage: str = "auto",
    taxid: int | None = None,
    taxon_lineage: str | None = None,
    accession: str | None = None,
    write_summary: bool = False,
) -> PaintOutputs:
    """Run the painter workflow and return generated output paths."""
    out_all, out_len, out_sum = resolve_output_paths(prefix)
    out_all.parent.mkdir(parents=True, exist_ok=True)

    selected_lineage = choose_reference_lineage(
        lineage=lineage,
        taxid=taxid,
        taxon_lineage=taxon_lineage,
        accession=accession,
    )
    ref_path = Path(reference_table) if reference_table else bundled_reference_table(
        selected_lineage
    )
    print(f"[INFO] Using {selected_lineage} ALG table: {ref_path}")

    busco_dataset = parse_busco_dataset(query_table)
    if busco_dataset and busco_dataset != EXPECTED_BUSCO_LINEAGE:
        print(
            "[WARN] BUSCO table reports "
            f"{busco_dataset}; bundled ALG tables expect {EXPECTED_BUSCO_LINEAGE}"
        )

    ref_map = build_ref_map(ref_path)
    query_rows, query_chromosomes = parse_busco_table(query_table)
    chrom_order = query_chromosomes.copy()

    wrote_len = False
    if accession:
        sequence_report = fetch_sequence_report(accession)
        query_rows, remapped_chroms = remap_query_chromosomes(
            query_rows, sequence_name_to_genbank_map(sequence_report)
        )
        if remapped_chroms:
            print(
                "[INFO] Remapped "
                f"{remapped_chroms} BUSCO rows to NCBI GenBank accessions"
            )
        pairs = chrom_lengths_with_unloc(sequence_report)
        length_lines = ["Chrom\tLength_Mb"] + [
            f"{chrom}\t{basepairs / 1e6:.3f}" for chrom, basepairs in pairs
        ]
        write_tsv(length_lines, out_len)
        wrote_len = True
        chrom_order = [chrom for chrom, _ in pairs]

    all_rows, mapped_buscos = build_location_rows(ref_map, query_rows)
    if query_rows:
        pct_mapped = mapped_buscos / len(query_rows) * 100
        print(
            "[INFO] Mapped "
            f"{mapped_buscos}/{len(query_rows)} BUSCO rows to ALGs "
            f"({pct_mapped:.1f}%)"
        )
    else:
        print("[WARN] No Complete or Duplicated BUSCO rows found")

    query_chroms = {chrom for _, chrom, _, _ in query_rows}
    missing = [chrom for chrom in chrom_order if chrom not in query_chroms]
    for chrom in missing:
        all_rows.append(f"NA\t{chrom}\tNA\tNA\tunassigned")

    write_tsv(all_rows, out_all)

    wrote_sum = False
    if write_summary:
        counts = Counter(chrom for _, chrom, _, _ in query_rows)
        counts.update({chrom: 0 for chrom in missing})
        summary_lines = ["query_chr\tbusco_hits"] + [
            f"{chrom}\t{counts[chrom]}" for chrom in chrom_order
        ]
        write_tsv(summary_lines, out_sum)
        wrote_sum = True

    return PaintOutputs(
        all_locations=out_all,
        chrom_lengths=out_len,
        summary=out_sum,
        wrote_lengths=wrote_len,
        wrote_summary=wrote_sum,
        lineage=selected_lineage,
        reference_table=ref_path,
        busco_dataset=busco_dataset,
        mapped_buscos=mapped_buscos,
        total_buscos=len(query_rows),
    )
