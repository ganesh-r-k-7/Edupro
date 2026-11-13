# edup.analytics — Business analytics and KPI computation
from .analytics import (
    amount_price_identity_summary,
    break_even_enrollment_change,
    compute_business_facts,
    compute_kpis,
    enrollment_reference,
    price_demand_diagnostics,
    revenue_scenarios,
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
