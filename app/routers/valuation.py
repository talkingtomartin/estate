import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user, get_flashes
from app.templates_config import templates
from app.routers.properties import _accessible_owner_ids

router = APIRouter(prefix="/verdiutvikling", tags=["valuation"])


@router.get("")
async def valuation_overview(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    owner_ids = _accessible_owner_ids(db, user.id)

    properties = (
        db.query(models.Property)
        .filter(models.Property.user_id.in_(owner_ids))
        .order_by(models.Property.created_at)
        .all()
    )

    rows = []
    for prop in properties:
        total_inv = sum(i.amount for i in prop.investments)
        cost_basis = (prop.purchase_price or 0) + total_inv
        current_val = prop.current_value
        gain = (current_val - cost_basis) if (current_val is not None and cost_basis > 0) else None
        gain_pct = (gain / cost_basis * 100) if (gain is not None and cost_basis > 0) else None

        rows.append({
            "prop": prop,
            "purchase_price": prop.purchase_price,
            "total_investments": total_inv,
            "cost_basis": cost_basis if cost_basis > 0 else None,
            "current_value": current_val,
            "gain": gain,
            "gain_pct": gain_pct,
        })

    # Totals
    total_purchase = sum(r["purchase_price"] or 0 for r in rows)
    total_investments_all = sum(r["total_investments"] for r in rows)
    total_cost_basis = sum(r["cost_basis"] or 0 for r in rows)
    total_current = sum(r["current_value"] or 0 for r in rows)
    total_gain = (total_current - total_cost_basis) if (total_current and total_cost_basis) else None
    total_gain_pct = (total_gain / total_cost_basis * 100) if (total_gain is not None and total_cost_basis > 0) else None

    # Chart data – only properties with enough data for a meaningful bar
    chart_props = [r for r in rows if r["cost_basis"] or r["current_value"]]
    chart_labels = [r["prop"].name for r in chart_props]

    # Add a "Totalt" column if more than one property has data
    if len(chart_props) > 1 and total_cost_basis > 0:
        chart_labels.append("Totalt")

    chart_cost = [r["cost_basis"] or 0 for r in chart_props]
    chart_value = [r["current_value"] or 0 for r in chart_props]

    if len(chart_props) > 1 and total_cost_basis > 0:
        chart_cost.append(total_cost_basis)
        chart_value.append(total_current)

    chart_data = json.dumps({
        "labels": chart_labels,
        "cost": chart_cost,
        "value": chart_value,
    })

    return templates.TemplateResponse(request, "valuation/index.html", {
        "user": user,
        "rows": rows,
        "total_purchase": total_purchase,
        "total_investments_all": total_investments_all,
        "total_cost_basis": total_cost_basis,
        "total_current": total_current,
        "total_gain": total_gain,
        "total_gain_pct": total_gain_pct,
        "chart_data": chart_data,
        "flash_messages": get_flashes(request),
    })
