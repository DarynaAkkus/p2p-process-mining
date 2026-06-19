# Power BI Dashboard Design — Request-for-Payment Process Monitoring

This document specifies the structure for a Power BI dashboard built on top
of the process mining outputs in this repository (`images/*.csv` files map
directly to the tables described below). It is designed to be handed to a
BI developer or built directly by importing the CSV outputs as a data
source.

## Data Model

Import these tables (already produced by `analysis.py` / `advanced_analysis.py`):

| Table | Source file | Grain |
|---|---|---|
| `Cases` | derived from event log | one row per case (case_id, start, end, duration, n_events, was_rejected) |
| `Events` | event log itself | one row per event (case_id, activity, timestamp, resource) |
| `StepDurations` | `step_durations.csv` | one row per activity |
| `Variants` | `process_variants.csv` | one row per top variant |
| `RCASummary` | `rca_summary.csv`, `rca_rejection_impact.csv` | summary rows |
| `ROIEstimate` | `roi_estimate.csv` | one row per automation candidate |

Relationship: `Events[case_id]` → `Cases[case_id]` (many-to-one).

## Suggested DAX Measures

```dax
Avg Case Duration (days) =
AVERAGE ( Cases[duration_days] )

Median Case Duration (days) =
MEDIAN ( Cases[duration_days] )

Rework Rate % =
DIVIDE (
    CALCULATE ( COUNTROWS ( Cases ), Cases[was_rejected] = TRUE() ),
    COUNTROWS ( Cases )
)

Throughput (cases/week) =
CALCULATE (
    COUNTROWS ( Cases ),
    DATESINPERIOD ( Cases[end_date], MAX ( Cases[end_date] ), -7, DAY )
)

Duration Penalty - Rejected vs Clean =
DIVIDE (
    CALCULATE ( AVERAGE ( Cases[duration_days] ), Cases[was_rejected] = TRUE() ),
    CALCULATE ( AVERAGE ( Cases[duration_days] ), Cases[was_rejected] = FALSE() )
) - 1

Automation Hours Saved (Annual) =
SUM ( ROIEstimate[hours_saved_per_year] )

Automation Savings € (Annual) =
SUM ( ROIEstimate[estimated_annual_savings_eur] )
```

## Page-by-Page Layout

### Page 1 — Executive Overview
- **KPI cards (top row):** Total Cases, Avg Duration, Median Duration, Rework Rate %, Throughput/week
- **Line chart:** Weekly case volume / throughput trend over time
- **Donut chart:** Case status breakdown (clean vs. rejected-at-least-once)
- **Callout card:** "Top automation opportunity — Approved by Administration — €6,434/year potential savings"

### Page 2 — Bottleneck View
- **Horizontal bar chart:** Average time-to-next-step by activity (`StepDurations`), sorted descending
- **Process map image/visual:** embed `process_map.png` as a static image visual, or rebuild as a Sankey diagram using `Events` transitions
- **Slicer:** filter by activity / resource role
- **Table:** step duration mean/median/count, conditionally formatted (red = slowest steps)

### Page 3 — Process Variants
- **Pareto combo chart (bar + line):** variant frequency (bars) + cumulative % (line), matching `variant_pareto.png`
- **Table:** top 10 variants with case count, % of total, number of steps
- **Card:** "X variants cover 80% of cases" headline metric
- **Drill-through page:** click a variant → see sample case IDs following that path

### Page 4 — Rework & Root Cause
- **Clustered bar chart:** Avg duration — Rejected vs. Not Rejected cases
- **Bar chart:** Activities over-represented in slow (P90+) cases vs. fast cases
- **KPI card:** "Rejection Delay Factor: +52%"
- **Scatter plot:** Number of events per case vs. case duration (to visualize the r=0.36 correlation)

### Page 5 — Automation Business Case
- **Matrix/table:** Activity × Volume × Automation Potential × Priority (color-coded by priority: P1 red/orange, P2 yellow, P3 gray)
- **What-if parameters:** sliders for `Manual Minutes per Case`, `Hourly Cost`, `Robot Runtime Seconds` — feeding the ROI measures above, so a stakeholder can adjust assumptions live
- **Bar chart:** Manual hours vs. robot hours (mirrors `roi_chart.png`)
- **Card:** Total estimated annual savings across all P1 initiatives

## Visual Design Notes

- Use a consistent color code throughout: red/orange = problem area (bottlenecks, rejections), green = improvement/automation opportunity, blue/gray = neutral volume metrics
- Keep KPI cards at the top of every page for consistent at-a-glance context
- Use bookmarks to toggle between "As-Is" and "To-Be" views on the Automation page, if time allows

## Why this structure

The dashboard is organized to mirror the analytical narrative of the README
itself — overview → bottlenecks → variants → root cause → automation
business case — so that a stakeholder reading top to bottom experiences the
same logical flow as the written report, just interactively.
