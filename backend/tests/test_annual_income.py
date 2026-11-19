from datetime import date

from aperture import annual_income, calendar


def test_comparable_income_is_same_accessor_and_available_after_filing():
    cik = "0000012345"
    valid = "0000012345-24-000001"
    missing = "0000012345-25-000001"

    def fact(accession, filed, end, value, start=None, form="10-K"):
        return {
            "accn": accession,
            "filed": filed,
            "end": end,
            "val": value,
            "form": form,
            **({"start": start} if start else {}),
        }

    company = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            fact(valid, "2024-02-01", "2022-12-31", 500),
                            fact(missing, "2025-02-03", "2023-12-31", 530),
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            fact(valid, "2024-02-01", "2023-12-31", 80, "2023-01-01"),
                            fact(valid, "2024-02-01", "2022-12-31", -10, "2022-01-01"),
                            fact(
                                missing, "2025-02-03", "2024-12-31", 100, "2024-01-01"
                            ),
                            fact(
                                missing, "2025-02-03", "2024-12-31", 200, "2024-01-01"
                            ),
                        ]
                    }
                },
                "ProfitLoss": {
                    "units": {
                        "USD": [
                            fact(missing, "2025-02-03", "2023-12-31", 79, "2023-01-01"),
                        ]
                    }
                },
            }
        }
    }
    rows = annual_income.normalize(cik, company, {})

    def selected(day):
        return annual_income.as_of(rows, day, calendar.available_time(day))

    assert selected(date(2024, 2, 1)) is None
    first = selected(date(2024, 2, 2))
    assert first["net_income"] == "80"
    assert first["previous_net_income"] == "-10"
    assert first["beginning_assets"] == "500"
    assert selected(date(2025, 2, 3)) == first
    newest = selected(date(2025, 2, 4))
    assert newest["accession"] == missing
    assert "net_income" not in newest
