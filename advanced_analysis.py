"""
Advanced Process Mining Analysis — KPIs, Variants, Root Cause
===============================================================
Extends the base analysis with case-level KPIs, process variant analysis,
and root-cause investigation of why certain cases take longer than others.
"""

import pandas as pd
import numpy as np
import pm4py
import matplotlib.pyplot as plt

DATA_PATH = "data/RequestForPayment.xes.gz"

print("Loading event log...")
log = pm4py.read_xes(DATA_PATH)

df = log.rename(columns={
    "case:concept:name": "case_id",
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "org:resource": "resource",
    "org:role": "role",
})[["case_id", "activity", "timestamp", "resource", "role"]]

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)

n_cases = df["case_id"].nunique()
n_events = len(df)
print(f"{n_cases} cases, {n_events} events")

# =================================================================
# 1. CASE-LEVEL KPIs
# =================================================================
print("\n--- Case-level KPIs ---")

case_stats = df.groupby("case_id").agg(
    start=("timestamp", "min"),
    end=("timestamp", "max"),
    n_events=("activity", "count"),
)
case_stats["duration_hours"] = (
    (case_stats["end"] - case_stats["start"]).dt.total_seconds() / 3600
)
case_stats["duration_days"] = case_stats["duration_hours"] / 24

avg_duration_days = case_stats["duration_days"].mean()
median_duration_days = case_stats["duration_days"].median()
p90_duration_days = case_stats["duration_days"].quantile(0.90)
avg_events_per_case = case_stats["n_events"].mean()

# Throughput: cases completed per week, based on end timestamps
case_stats["end_week"] = case_stats["end"].dt.to_period("W")
throughput_per_week = case_stats.groupby("end_week").size()

kpi_summary = pd.DataFrame([{
    "total_cases": n_cases,
    "total_events": n_events,
    "avg_duration_days": round(avg_duration_days, 2),
    "median_duration_days": round(median_duration_days, 2),
    "p90_duration_days": round(p90_duration_days, 2),
    "avg_events_per_case": round(avg_events_per_case, 1),
    "avg_throughput_per_week": round(throughput_per_week.mean(), 1),
    "fastest_case_days": round(case_stats["duration_days"].min(), 3),
    "slowest_case_days": round(case_stats["duration_days"].max(), 1),
}])
kpi_summary.to_csv("images/kpi_summary.csv", index=False)
print(kpi_summary.T)

# Distribution chart of case durations
plt.figure(figsize=(8, 5))
plt.hist(case_stats["duration_days"].clip(upper=120), bins=40, color="#2980b9")
plt.axvline(median_duration_days, color="#e74c3c", linestyle="--",
            label=f"Median = {median_duration_days:.1f} days")
plt.axvline(avg_duration_days, color="#f39c12", linestyle="--",
            label=f"Mean = {avg_duration_days:.1f} days")
plt.xlabel("Case duration (days, capped at 120 for readability)")
plt.ylabel("Number of cases")
plt.title("Distribution of Request-for-Payment process duration")
plt.legend()
plt.tight_layout()
plt.savefig("images/duration_distribution.png", dpi=150)
plt.close()
print("Saved images/duration_distribution.png")

# =================================================================
# 2. PROCESS VARIANTS
# =================================================================
print("\n--- Process variants ---")

variants = (
    df.groupby("case_id")["activity"]
    .apply(lambda acts: " -> ".join(acts))
)
variant_counts = variants.value_counts()
n_variants = len(variant_counts)
top_variants = variant_counts.head(10)
top10_coverage = top_variants.sum() / n_cases * 100

variant_summary = pd.DataFrame({
    "variant_rank": range(1, len(top_variants) + 1),
    "n_cases": top_variants.values,
    "pct_of_total": (top_variants.values / n_cases * 100).round(1),
    "n_steps": [len(v.split(" -> ")) for v in top_variants.index],
    "path": top_variants.index,
})
variant_summary.to_csv("images/process_variants.csv", index=False)
print(f"Total distinct variants: {n_variants}")
print(f"Top 10 variants cover {top10_coverage:.1f}% of all cases")
print(variant_summary[["variant_rank", "n_cases", "pct_of_total", "n_steps"]])

# Variant coverage chart (Pareto-style)
cumulative_pct = (variant_counts.cumsum() / n_cases * 100)
plt.figure(figsize=(8, 5))
plt.plot(range(1, min(50, n_variants) + 1), cumulative_pct.values[:50],
          color="#8e44ad", marker="o", markersize=3)
plt.axhline(80, color="gray", linestyle=":", label="80% of cases")
plt.xlabel("Number of variants (ranked by frequency)")
plt.ylabel("Cumulative % of cases covered")
plt.title("Process variant concentration (Pareto view)")
plt.legend()
plt.tight_layout()
plt.savefig("images/variant_pareto.png", dpi=150)
plt.close()
print("Saved images/variant_pareto.png")

n_variants_for_80pct = int((cumulative_pct <= 80).sum()) + 1
print(f"Variants needed to cover 80% of cases: {n_variants_for_80pct} "
      f"out of {n_variants} total variants")

# =================================================================
# 3. ROOT CAUSE ANALYSIS: why do some cases take longer?
# =================================================================
print("\n--- Root cause analysis ---")

# Does rejection/rework correlate with longer duration?
rejection_keywords = ["Reject", "Reset"]
case_rejected = (
    df[df["activity"].str.contains("|".join(rejection_keywords), case=False, na=False)]
    ["case_id"].unique()
)
case_stats["was_rejected"] = case_stats.index.isin(case_rejected)

rca_rejection = case_stats.groupby("was_rejected")["duration_days"].agg(
    ["mean", "median", "count"]
)
rca_rejection.to_csv("images/rca_rejection_impact.csv")
print("Duration by rejection status:")
print(rca_rejection)

mean_no_reject = rca_rejection.loc[False, "mean"]
mean_reject = rca_rejection.loc[True, "mean"]
rejection_delay_factor = mean_reject / mean_no_reject

# Does number of events (complexity) correlate with duration?
correlation_events_duration = case_stats["n_events"].corr(case_stats["duration_days"])

# Which activity is most associated with the slowest 10% of cases?
slow_threshold = case_stats["duration_days"].quantile(0.90)
slow_cases = case_stats[case_stats["duration_days"] >= slow_threshold].index
fast_cases = case_stats[case_stats["duration_days"] < slow_threshold].index

activity_in_slow = df[df["case_id"].isin(slow_cases)]["activity"].value_counts(normalize=True)
activity_in_fast = df[df["case_id"].isin(fast_cases)]["activity"].value_counts(normalize=True)
activity_overrep = (activity_in_slow - activity_in_fast).sort_values(ascending=False)
activity_overrep.to_csv("images/rca_activity_overrepresentation.csv")

print("\nActivities over-represented in the slowest 10% of cases "
      "(share in slow cases minus share in fast cases):")
print(activity_overrep.head(8))

rca_summary = pd.DataFrame([{
    "mean_duration_no_rejection_days": round(mean_no_reject, 1),
    "mean_duration_with_rejection_days": round(mean_reject, 1),
    "rejection_delay_factor": round(rejection_delay_factor, 2),
    "correlation_events_vs_duration": round(correlation_events_duration, 2),
    "slow_case_threshold_days": round(slow_threshold, 1),
}])
rca_summary.to_csv("images/rca_summary.csv", index=False)
print("\nRCA summary:")
print(rca_summary.T)

print("\nDone. All advanced analysis results saved in images/ folder.")
