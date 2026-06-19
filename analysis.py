"""
P2P Process Mining — Request for Payment Bottleneck Analysis
==============================================================
Analyzes a real-life event log (BPI Challenge 2020, "Request For Payment")
to discover the process flow, find bottlenecks, measure rejection/rework
rate, and identify candidates for RPA automation.

Data source: BPI Challenge 2020, 4TU.ResearchData / bptlab cleaned logs.
"""

import pandas as pd
import pm4py
import matplotlib.pyplot as plt

DATA_PATH = "data/RequestForPayment.xes.gz"

# ---------------------------------------------------------------
# 1. Load the event log
# ---------------------------------------------------------------
print("Loading event log...")
log = pm4py.read_xes(DATA_PATH)

# Keep only the columns we actually need, with friendly names
df = log.rename(columns={
    "case:concept:name": "case_id",
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "org:resource": "resource",
    "org:role": "role",
})[["case_id", "activity", "timestamp", "resource", "role"]]

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)

print(f"Loaded {df['case_id'].nunique()} cases, {len(df)} events, "
      f"{df['activity'].nunique()} distinct activities.")

# ---------------------------------------------------------------
# 2. Discover and visualize the process map (Directly-Follows Graph)
# ---------------------------------------------------------------
print("Discovering process map...")
log_for_pm4py = log.rename(columns={
    "case:concept:name": "case:concept:name",
    "concept:name": "concept:name",
    "time:timestamp": "time:timestamp",
})

dfg, start_activities, end_activities = pm4py.discover_dfg(
    log, activity_key="concept:name",
    timestamp_key="time:timestamp", case_id_key="case:concept:name"
)

pm4py.save_vis_dfg(
    dfg, start_activities, end_activities,
    "images/process_map.png",
    activity_key="concept:name",
    timestamp_key="time:timestamp", case_id_key="case:concept:name"
)
print("Saved images/process_map.png")

# ---------------------------------------------------------------
# 3. Measure time spent on each step (bottleneck analysis)
# ---------------------------------------------------------------
print("Computing step durations...")

# Time between consecutive activities within the same case
df["next_activity"] = df.groupby("case_id")["activity"].shift(-1)
df["next_timestamp"] = df.groupby("case_id")["timestamp"].shift(-1)
df["duration_hours"] = (
    (df["next_timestamp"] - df["timestamp"]).dt.total_seconds() / 3600
)

step_duration = (
    df.dropna(subset=["duration_hours"])
    .groupby("activity")["duration_hours"]
    .agg(["mean", "median", "count"])
    .sort_values("mean", ascending=False)
)
step_duration.to_csv("images/step_durations.csv")
print(step_duration.head(10))

# Bar chart of slowest steps
top_slow = step_duration.head(10).iloc[::-1]
plt.figure(figsize=(8, 5))
plt.barh(top_slow.index, top_slow["mean"], color="#c0392b")
plt.xlabel("Average time to next step (hours)")
plt.title("Top 10 slowest steps — Request for Payment process")
plt.tight_layout()
plt.savefig("images/bottleneck_chart.png", dpi=150)
plt.close()
print("Saved images/bottleneck_chart.png")

# ---------------------------------------------------------------
# 4. Rejection / rework rate
# ---------------------------------------------------------------
print("Computing rejection rate...")
rejection_keywords = ["Reject", "Reset", "Rejected"]
cases_with_rejection = df[
    df["activity"].str.contains("|".join(rejection_keywords), case=False, na=False)
]["case_id"].nunique()
total_cases = df["case_id"].nunique()
rejection_rate = cases_with_rejection / total_cases * 100
print(f"Cases with at least one rejection/resubmission: "
      f"{cases_with_rejection} / {total_cases} ({rejection_rate:.1f}%)")

# ---------------------------------------------------------------
# 5. Resource workload (who handles the most, who is slowest)
# ---------------------------------------------------------------
print("Computing resource workload...")
resource_stats = (
    df.dropna(subset=["duration_hours"])
    .groupby("resource")["duration_hours"]
    .agg(["mean", "count"])
    .query("count >= 30")  # ignore resources with too few events
    .sort_values("mean", ascending=False)
)
resource_stats.to_csv("images/resource_stats.csv")
print(resource_stats.head(5))

# ---------------------------------------------------------------
# 6. Activity frequency (which steps are most repetitive -> RPA candidates)
# ---------------------------------------------------------------
activity_freq = df["activity"].value_counts()
activity_freq.to_csv("images/activity_frequency.csv")

print("\nDone. All results saved in images/ folder.")
