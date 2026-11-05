"""Economic exposure disclosures derived from frozen NAV and target records."""

from decimal import Decimal


def summarize(result):
    curve = result.get("curve", [])
    if not curve:
        return None
    cash, stock = [], []
    for row in curve:
        equity = Decimal(row["equity"])
        if equity <= 0:
            continue
        c = Decimal(row["cash"]) / equity
        r = Decimal(row.get("receivable", "0")) / equity
        cash.append(c)
        stock.append(1 - c - r)
    targets = [
        sum((Decimal(w) for w in row.get("targets", {}).values()), Decimal(0))
        for row in result.get("decisions", [])
    ]
    return {
        "mean_stock_weight": float(sum(stock) / len(stock)),
        "mean_cash_weight": float(sum(cash) / len(cash)),
        "min_target_stock_weight": float(min(targets)) if targets else None,
        "max_target_stock_weight": float(max(targets)) if targets else None,
        "basis": "Daily closing stock value / NAV; includes the initial all-cash valuation. Receivables are separate from stocks and cash.",
    }
