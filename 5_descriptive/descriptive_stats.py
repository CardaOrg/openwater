#!/usr/bin/env python3
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

# IMPORTANT for batch jobs (no display): use a non-interactive backend
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def get_descriptive_stats(df, target_column=None):
    
    print(df.columns)
    print("Checks ter controle kwaliteit data")

    if 'y_1x_check_aantal_rijen_in_WOK_Player_Profile' in df.columns:
        print()
        print('Elke keer dat een profielstatus wijzigd, moet er een XML worden opgenomen.') 
        print('Maar ook elke keer als in die dag een inzet wordt gedaan, moet er een rij in WOK_Player_Profile staan')
        print('Daarnaast is er eens per jaar op 1 oktober een rij per actieve speler.')        
        print(f"Gemiddeld aantal rijen in WOK_Player_Profile: {df['y_1x_check_aantal_rijen_in_WOK_Player_Profile'].mean()}")
        print(f"Aantal met 1 rij: {(df['y_1x_check_aantal_rijen_in_WOK_Player_Profile'] == 1).sum()}")

    
    if target_column and target_column in df.columns:
        target_distribution = df[target_column].value_counts(normalize=True, dropna=False)
        print(f"Target Variable Distribution:\n{target_distribution}\n")

    for col in df.select_dtypes(include=[np.number]).columns:
        print(f"Descriptive statistics for {col}:\n{df[col].describe()}\n")

    for col in df.select_dtypes(include=[object]).columns:
        print(f"Value counts for {col}:\n{df[col].value_counts(dropna=False)}\n")

    feature_cols = [col for col in df.columns if col.startswith("x")]
    if target_column and target_column in df.columns:
        feature_cols.append(target_column)

    if feature_cols:
        corr_matrix = df[feature_cols].corr(numeric_only=True)
        print(f"Correlation matrix:\n{corr_matrix}\n")


def save_target_distribution_plot(df, target, out_path: Path):
    counts = df[target].value_counts(dropna=False).sort_index()
    ax = counts.plot(kind="bar")
    ax.set_title(f"Target distribution: {target}")
    ax.set_xlabel("Class")
    ax.set_ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def save_corr_heatmap(df, cols, out_path: Path):
    corr = df[cols].corr(numeric_only=True)

    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(corr.values, aspect="auto")  # no explicit colormap to keep it minimal
    ax.set_title("Correlation heatmap")

    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=90, fontsize=6)
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index, fontsize=6)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def save_histograms(df, numeric_cols, dated_out_dir: Path, prefix: str, max_plots: int = 20):
    cols = list(numeric_cols)[:max_plots]
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        plt.figure(figsize=(8, 4))
        plt.hist(s.values, bins=50)
        plt.title(f"Histogram: {c}")
        plt.xlabel(c)
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(dated_out_dir / f"{prefix}_hist_{c}.png", dpi=200)
        plt.close()


# NB (organisatie-versie): de body van `main()` is uitgelicht naar `generate_descriptive_report(...)`,
# zodat de runner het in-process kan aanroepen (zonder subprocess/sbatch). `main()` blijft een
# dunne CLI-wrapper met identieke argumenten en gedrag.
def generate_descriptive_report(input_path, output_dir, target=None) -> Path:
    """
    Lees een feature-CSV en schrijf een tekstrapport + plots naar
    `{output_dir}/{stamp}/`. Retourneert de aangemaakte dated output-map.

    Plots: target-verdeling (bar), correlatie-heatmap en histogrammen over de
    feature-kolommen die met 'x' beginnen (de conventie uit het origineel).
    """
    input_path = Path(input_path)
    base_out_dir = Path(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated_out_dir = base_out_dir / stamp
    dated_out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    prefix = input_path.stem  # e.g. "a"

    # 1) write the text report, get descriptive stats for the target variable
    out_txt = dated_out_dir / f"{prefix}_descriptive_stats.txt"
    with out_txt.open("w") as f:
        import contextlib
        with contextlib.redirect_stdout(f):
            get_descriptive_stats(df, target)

    # 2) plots
    if target and target in df.columns:
        save_target_distribution_plot(df, target, dated_out_dir / f"{prefix}_target_distribution.png")

    x_cols = [c for c in df.columns if c.startswith("x")]
    x_numeric = [c for c in x_cols if pd.api.types.is_numeric_dtype(df[c])]

    corr_cols = list(x_numeric)
    if target and target in df.columns and pd.api.types.is_numeric_dtype(df[target]):
        corr_cols.append(target)

    if len(corr_cols) >= 2:
        save_corr_heatmap(df, corr_cols, dated_out_dir / f"{prefix}_corr_heatmap.png")

    # Keep histogram count limited
    save_histograms(df, x_numeric, dated_out_dir, prefix=prefix, max_plots=20)

    print(f"[DONE] Wrote {out_txt} and plots to {dated_out_dir}")
    return dated_out_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--target", default=None)
    args = parser.parse_args()

    generate_descriptive_report(args.input, args.output_dir, args.target)


if __name__ == "__main__":
    main()