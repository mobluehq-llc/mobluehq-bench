"""CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import click

from mobluehq_bench.datasets import dataset_licenses, load_manifest
from mobluehq_bench.harness import run_benchmark


@click.group()
@click.version_option(package_name="mobluehq-bench")
def main() -> None:
    """MOBLUEHQ process-integrity benchmark."""


@main.command("run")
@click.option("--rail", "rail_spec", required=True, help="Rail adapter (mock-rail or https://...)")
@click.option(
    "--baseline",
    "baseline_spec",
    required=True,
    help="Baseline adapter (mock-baseline or openai://host/model)",
)
@click.option("--output", "output_dir", type=click.Path(), default="results/runs/latest")
@click.option("--seed", default=42, show_default=True, help="Deterministic seed")
@click.option("--max-samples", type=int, default=None, help="Cap items for quick runs")
def run_cmd(
    rail_spec: str,
    baseline_spec: str,
    output_dir: str,
    seed: int,
    max_samples: int | None,
) -> None:
    """Score rail vs baseline and emit signed results."""
    payload = run_benchmark(
        rail_spec=rail_spec,
        baseline_spec=baseline_spec,
        output_dir=Path(output_dir),
        seed=seed,
        max_samples=max_samples,
    )
    m = payload["metrics"]
    click.echo("Process-integrity benchmark complete.")
    click.echo(f"  Verified Answer Rate:      {m['verified_answer_rate']:.1%}")
    auroc = m["dissent_auroc"]
    click.echo(f"  Dissent AUROC:             {auroc:.3f}" if auroc is not None else "  Dissent AUROC:             n/a")
    sel_r = m["selective_accuracy_rail"]
    sel_b = m["selective_accuracy_baseline"]
    click.echo(f"  Selective accuracy (rail): {sel_r:.1%}" if sel_r is not None else "  Selective accuracy (rail): n/a")
    click.echo(
        f"  Selective accuracy (base): {sel_b:.1%}" if sel_b is not None else "  Selective accuracy (base): n/a"
    )
    delta = m["selective_accuracy_delta"]
    if delta is not None:
        click.echo(f"  Selective accuracy Δ:      {delta:+.1%}")
    ece = m["ece_rail"]
    click.echo(f"  ECE (rail):                {ece:.3f}" if ece is not None else "  ECE (rail):                n/a")
    click.echo(f"  Unanimous-wrong residual:  {m['unanimous_wrong_count']}")
    click.echo(f"  Output: {output_dir}/")


@main.command("datasets")
def datasets_cmd() -> None:
    """List pinned public dataset slices."""
    manifest = load_manifest()
    click.echo(json.dumps({"manifest": manifest, "licenses": dataset_licenses()}, indent=2))


if __name__ == "__main__":
    main()
