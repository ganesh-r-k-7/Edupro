# edup.analytics — Business analytics and KPI computation
from .analytics import (
    compute_kpis,
    compute_business_facts,
    enrollment_reference,
    price_demand_diagnostics,
    revenue_scenarios,
    break_even_enrollment_change,
    amount_price_identity_summary,
)

__all__ = [
    "compute_kpis",
    "compute_business_facts",
    "enrollment_reference",
    "price_demand_diagnostics",
    "revenue_scenarios",
    "break_even_enrollment_change",
    "amount_price_identity_summary",
]