"""The normal acquisition unit always contains market and SEC inputs."""

from .domain import ResearchError
from .providers import Provider


def download(store, payload, progress, provider=None, *, base=None, refresh=False):
    from .research_data import download as prices
    from .fundamentals import attach

    api = provider or Provider(store)
    try:
        if "@" not in api.cfg.sec_agent:
            raise ResearchError(
                "Configure SEC_USER_AGENT with a contact email before downloading market data and SEC filings."
            )
        saved = prices(
            store, payload, lambda n, t: progress(round(n * 0.70), t), api, base=base
        )
        try:
            return attach(
                store,
                saved["id"],
                lambda n, t: progress(70 + round(n * 0.28), t),
                api,
                refresh=refresh,
                allow_empty=True,
            )
        except ResearchError as error:
            raise ResearchError(
                f"Prices were saved, but the SEC stage did not finish. In Data, use Complete SEC download to retry the saved snapshot ({saved['id']}). {error}"
            ) from None
    finally:
        if provider is None:
            api.close()
