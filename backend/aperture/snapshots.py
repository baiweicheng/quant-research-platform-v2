"""Human dataset families; internal price parents are storage components."""

import json


def family(summary):
    meta = summary.get("metadata", {})
    if meta.get("series_id"):
        return meta["series_id"]
    name = summary["name"]
    if meta.get("price_dataset_id") and name.endswith(" + SEC"):
        name = name[:-6]
    audit = meta.get("membership")
    query = meta.get("download", {})
    names = (
        audit.get("additional_symbols", [])
        if audit
        else query.get("symbols", summary["symbols"])
    )
    return json.dumps(
        [
            summary["kind"],
            meta.get("provider"),
            name,
            query.get("start", summary["start"]),
            "sp500" if audit else "custom",
            sorted(names),
        ]
    )


def latest(store, identifier):
    rows = store.datasets()
    selected = next(d for d in rows if d["id"] == identifier)
    candidates = [d for d in rows if family(d) == family(selected)]
    complete = [d for d in candidates if d.get("metadata", {}).get("fundamentals")]
    return max(complete or candidates, key=lambda d: (d["end"], d["created_at"]))
