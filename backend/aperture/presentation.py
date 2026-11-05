"""Bound screen payloads without changing persisted research or full exports."""

from .domain import ResearchError


def dataset_view(dataset: dict) -> dict:
    meta = {
        k: v
        for k, v in (dataset.get("metadata") or {}).items()
        if k not in {"input_issues", "observation_ids", "research_open_income"}
    }
    if isinstance(meta.get("membership"), dict):
        membership = meta["membership"]
        meta["membership"] = {
            k: v for k, v in membership.items() if k not in {"historical", "current"}
        }
    if isinstance(meta.get("identity_resolution"), dict):
        meta["identity_resolution"] = {
            symbol: {
                k: v
                for k, v in evidence.items()
                if k in {"reviewed_alias", "original_actions_reconciled"}
            }
            for symbol, evidence in meta["identity_resolution"].items()
            if isinstance(evidence, dict) and "reviewed_alias" in evidence
        }
    if isinstance(meta.get("sector_classification"), dict):
        meta["sector_classification"] = {
            k: v for k, v in meta["sector_classification"].items() if k != "records"
        }
    return {**dataset, "metadata": meta}


def result_view(result: dict, path: str) -> dict:
    if "curve" not in result:
        return result
    from .exposure import summarize

    return {
        **{k: v for k, v in result.items() if k != "input_audit"},
        "exposure": result.get("exposure") or summarize(result),
        "audit_path": path,
        "trades": result["trades"][-50:],
        "decisions": [
            {k: v for k, v in d.items() if k not in {"signals", "exclusions"}}
            for d in result.get("decisions", [])
        ],
    }


def decision_view(result: dict, session: str) -> dict:
    for decision in result.get("decisions", []):
        if decision["session"] == session:
            return decision
    raise ResearchError("That decision was not found in the saved research audit.")
