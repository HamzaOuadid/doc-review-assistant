"""Command-line interface. `pip install -e .` exposes this as `doc-review`."""
import json

import typer

from doc_review.corpus import load_corpus, load_hand_labels
from doc_review.evaluation import (
    confidently_wrong_rate,
    force_binary,
    grounding_accuracy,
    reviewer_time_saved,
    three_state,
)
from doc_review.extraction import extract as run_extract
from doc_review.llm.factory import get_default_llm_client
from doc_review.schema import MSA_REVIEW_SCHEMA

app = typer.Typer(add_completion=False, help="Regulated-document review assistant CLI")


@app.command()
def extract(document_id: str = typer.Argument(..., help="corpus document id, e.g. adial_msa")) -> None:
    """Run extraction on one corpus document and print each field's result."""
    documents = {d.id: d for d in load_corpus()}
    if document_id not in documents:
        typer.echo(f"Unknown document_id {document_id!r}. Available: {', '.join(sorted(documents))}")
        raise typer.Exit(1)
    llm = get_default_llm_client()
    typer.echo(f"backend: {llm.name}\n")
    results = run_extract(documents[document_id], MSA_REVIEW_SCHEMA, llm)
    for r in results:
        _print_extraction(r)


@app.command()
def demo() -> None:
    """Run extraction across the whole corpus and print a curated mix of
    confident-include, confident-exclude, and uncertain results -- a
    concrete look at what the 'uncertain' state buys you."""
    documents = load_corpus()
    llm = get_default_llm_client()
    typer.echo(f"backend: {llm.name}\n")

    all_results = []
    for doc in documents:
        for r in run_extract(doc, MSA_REVIEW_SCHEMA, llm):
            all_results.append(r)

    by_class = {"include": [], "exclude": [], "uncertain": []}
    for r in all_results:
        by_class[r.classification].append(r)

    typer.secho("=== INCLUDE (grounded, high-confidence) ===", fg=typer.colors.GREEN, bold=True)
    for r in by_class["include"][:4]:
        _print_extraction(r)
    typer.secho(f"\n=== UNCERTAIN (flagged for reviewer, not guessed) ===", fg=typer.colors.YELLOW, bold=True)
    for r in by_class["uncertain"]:
        _print_extraction(r)
    typer.secho("\n=== EXCLUDE (confidently absent / explicitly negated) ===", fg=typer.colors.RED, bold=True)
    for r in by_class["exclude"]:
        _print_extraction(r)

    typer.echo(
        f"\nTotals across {len(documents)} documents x {len(MSA_REVIEW_SCHEMA.fields)} fields "
        f"= {len(all_results)} extractions: "
        f"{len(by_class['include'])} include, {len(by_class['exclude'])} exclude, "
        f"{len(by_class['uncertain'])} uncertain "
        f"({len(by_class['uncertain']) / len(all_results) * 100:.1f}% uncertain rate)"
    )


@app.command()
def evaluate(json_out: bool = typer.Option(False, "--json", help="print raw JSON instead of a formatted report")) -> None:
    """Run the full evaluation: confidently-wrong rate (binary vs. three-
    state), citation-grounding accuracy, and the reviewer-time-saved
    estimate, all against the hand-labeled corpus sample."""
    documents = load_corpus()
    hand_labels = load_hand_labels()
    llm = get_default_llm_client()

    all_extractions = []
    for doc in documents:
        all_extractions.extend(run_extract(doc, MSA_REVIEW_SCHEMA, llm))

    three = confidently_wrong_rate(three_state(all_extractions), hand_labels)
    binary = confidently_wrong_rate(force_binary(all_extractions), hand_labels)
    grounding = grounding_accuracy(all_extractions)
    time_saved = reviewer_time_saved(all_extractions, hand_labels)

    payload = {
        "backend": llm.name,
        "n_documents": len(documents),
        "n_hand_labels": len(hand_labels),
        "n_extractions": len(all_extractions),
        "three_state": {
            "confidently_wrong_rate_of_all": round(three.confidently_wrong_rate_of_all, 4),
            "confidently_wrong_rate_of_confident": round(three.confidently_wrong_rate_of_confident, 4),
            "uncertain_rate": round(three.uncertain_rate, 4),
            "confidently_wrong_count": three.confidently_wrong,
            "uncertain_count": three.uncertain_count,
        },
        "forced_binary": {
            "confidently_wrong_rate_of_all": round(binary.confidently_wrong_rate_of_all, 4),
            "confidently_wrong_count": binary.confidently_wrong,
        },
        "grounding": grounding,
        "reviewer_time_saved": time_saved,
    }

    if json_out:
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"backend: {llm.name}")
    typer.echo(f"corpus: {len(documents)} documents, {len(hand_labels)} hand labels, {len(all_extractions)} extractions\n")
    typer.secho("Confidently-wrong rate (of ALL scored predictions):", bold=True)
    typer.echo(f"  forced-binary (no uncertain state): {binary.confidently_wrong_rate_of_all:.1%}  ({binary.confidently_wrong}/{binary.total})")
    typer.echo(f"  three-state (with uncertain state):  {three.confidently_wrong_rate_of_all:.1%}  ({three.confidently_wrong}/{three.total})")
    typer.echo(f"  uncertain rate: {three.uncertain_rate:.1%}  ({three.uncertain_count}/{three.total})\n")
    typer.secho("Citation grounding (of INCLUDE predictions):", bold=True)
    typer.echo(f"  {grounding['grounded_count']}/{grounding['included_count']} grounded ({grounding['grounding_rate']:.1%})\n")
    typer.secho("Reviewer time saved (stated-assumption estimate):", bold=True)
    typer.echo(f"  {time_saved['percent_time_saved']:.1f}% saved, {time_saved['saved_seconds_per_document']:.0f}s/document "
               f"across {time_saved['n_documents']} documents")


def _print_extraction(r) -> None:
    typer.echo(f"[{r.classification.upper():9s}] {r.document_id} / {r.field_name}")
    if r.extracted_value:
        typer.echo(f"    value: {r.extracted_value}")
    if r.citation_span:
        typer.echo(f"    cite:  “{r.citation_span.strip()}”")
    if r.reason:
        typer.echo(f"    why:   {r.reason}")
    typer.echo("")


if __name__ == "__main__":
    app()
