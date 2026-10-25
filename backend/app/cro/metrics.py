"""CRO metric formulas.

A missing input stays missing. These functions do not substitute zero, and they
do not turn an assumed lift into revenue.
"""
from __future__ import annotations

import math
from typing import Optional


def rate(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Return numerator ÷ denominator when both are known and the denominator is positive."""
    if numerator is None or denominator is None:
        return None
    if isinstance(numerator, bool) or isinstance(denominator, bool):
        return None
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return None
    if not math.isfinite(float(numerator)) or not math.isfinite(float(denominator)):
        return None
    if denominator <= 0 or numerator < 0:
        return None
    return numerator / denominator


def experiment_lift(variant_rate: Optional[float], control_rate: Optional[float]) -> Optional[float]:
    """(variant − control) ÷ control. A zero or missing control makes lift undefined."""
    if variant_rate is None or control_rate is None:
        return None
    if isinstance(variant_rate, bool) or isinstance(control_rate, bool):
        return None
    if not isinstance(variant_rate, (int, float)) or not isinstance(control_rate, (int, float)):
        return None
    if not math.isfinite(float(variant_rate)) or not math.isfinite(float(control_rate)):
        return None
    if control_rate <= 0 or variant_rate < 0:
        return None
    return (variant_rate - control_rate) / control_rate


def incremental_profit(
    incremental_gross_profit: Optional[float],
    incremental_costs: Optional[float],
) -> Optional[float]:
    if incremental_gross_profit is None or incremental_costs is None:
        return None
    return incremental_gross_profit - incremental_costs


METRIC_CATALOG = (
    {
        "metric": "Conversion rate",
        "formula": "Unique eligible converters ÷ eligible users",
        "numerator_name": "unique converters",
        "denominator_name": "eligible users",
    },
    {
        "metric": "Key-event rate per session",
        "formula": "GA4 key events ÷ sessions",
        "numerator_name": "key events",
        "denominator_name": "sessions",
    },
    {
        "metric": "CTA engagement rate",
        "formula": "Unique visitors clicking the CTA ÷ eligible visitors exposed to it",
        "numerator_name": "cta clicks",
        "denominator_name": "visitors exposed",
    },
    {
        "metric": "Form completion rate",
        "formula": "Valid form submissions ÷ form starts",
        "numerator_name": "valid submissions",
        "denominator_name": "form starts",
    },
    {
        "metric": "Funnel completion rate",
        "formula": "Users completing the final stage ÷ users entering the defined funnel",
        "numerator_name": "final stage completions",
        "denominator_name": "funnel entries",
    },
    {
        "metric": "Stage drop-off rate",
        "formula": "Eligible users failing to advance ÷ eligible users entering the stage",
        "numerator_name": "users not advancing",
        "denominator_name": "stage entries",
    },
    {
        "metric": "Checkout completion rate",
        "formula": "Completed purchases ÷ eligible checkout starters",
        "numerator_name": "completed purchases",
        "denominator_name": "checkout starters",
    },
    {
        "metric": "Qualified lead rate",
        "formula": "Qualified leads ÷ total valid leads",
        "numerator_name": "qualified leads",
        "denominator_name": "valid leads",
    },
    {
        "metric": "Lead-to-customer rate",
        "formula": "Customers acquired ÷ eligible leads in the defined cohort",
        "numerator_name": "customers",
        "denominator_name": "eligible leads",
    },
    {
        "metric": "Revenue per visitor",
        "formula": "Attributed revenue ÷ eligible visitors",
        "numerator_name": "attributed revenue",
        "denominator_name": "eligible visitors",
    },
    {
        "metric": "Average order value",
        "formula": "Net sales ÷ completed orders",
        "numerator_name": "net sales",
        "denominator_name": "completed orders",
    },
    {
        "metric": "Trial-to-paid rate",
        "formula": "Trial users becoming paying customers ÷ eligible trial cohort",
        "numerator_name": "paid conversions",
        "denominator_name": "eligible trials",
    },
    {
        "metric": "Experiment lift",
        "formula": "(Variant conversion rate − control conversion rate) ÷ control conversion rate",
        "numerator_name": "variant rate minus control rate",
        "denominator_name": "control rate",
    },
    {
        "metric": "Incremental profit",
        "formula": "Estimated incremental gross profit minus incremental costs",
        "numerator_name": "incremental gross profit",
        "denominator_name": "incremental costs",
    },
)


MEASUREMENT_RULES = (
    "Define whether the denominator is users, sessions, visits, orders, or form starts. These are not interchangeable.",
    "Specify the observation window and attribution method.",
    "Deduplicate conversion events.",
    "Separate valid leads from spam and unqualified submissions.",
    "Report mobile and desktop differences without assuming the device caused the difference.",
    "Distinguish observed correlation from experimentally demonstrated effects.",
    "Do not forecast revenue by multiplying an assumed conversion lift by traffic without documenting the assumptions.",
)
