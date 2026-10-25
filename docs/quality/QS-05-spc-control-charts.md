---
title: QS-05 Statistical Process Control and Control Chart Rules
source: quality
doc_type: standard
site: Riverside Plant
---

# QS-05 Statistical Process Control and Control Chart Rules

## 1 Scope

Defines how operators plot and respond to control charts on critical characteristics, including BRK-200 hole position from PRS-2 and weld leg size from WLD-1. Charts are X-bar and R with subgroups of 5 parts taken every hour.

## 2 Out-of-Control Rules

| Rule | Pattern | Required Response |
|---|---|---|
| Rule 1 | One point beyond 3 sigma | Stop and investigate immediately |
| Rule 2 | 2 of 3 points beyond 2 sigma on same side | Investigate within the shift |
| Rule 3 | 7 consecutive points on one side of the center line | Check for process shift |
| Rule 4 | 6 points steadily increasing or decreasing | Check for tool wear or drift |

## 3 Process Capability Targets

| Cpk | Status | Action |
|---|---|---|
| 1.67 or above | Excellent | Reduce sampling frequency |
| 1.33 to 1.67 | Capable | Continue normal sampling |
| 1.00 to 1.33 | Marginal | 100% inspection until corrected |
| Below 1.00 | Not capable | Stop line and contain parts |

## 4 Response to an Out-of-Control Signal

1. Stop production and tag the suspect parts in the current lot.
2. Inspect the last 25 parts made since the previous good subgroup.
3. Check the machine for causes. A rising trend (Rule 4) on PRS-2 dimensions often indicates die wear; request maintenance to inspect the die.
4. Record the cause and the corrective action on the control chart.
5. Resume production only after two consecutive in-control subgroups.

Any repair requiring access inside machine guards needs lockout/tagout under SOP-07.
