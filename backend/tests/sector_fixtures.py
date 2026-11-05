import csv
import io


def archive_csv(rows=()):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        ["symbol", "cik", "name", "sector", "date_added", "date_removed", "created_at"]
    )
    for i in range(450):
        writer.writerow(
            [
                f"FIX{i}",
                str(i + 10000),
                f"Fixture issuer {i}",
                "industrials",
                "2000-01-01",
                "",
                "2007-03-05",
            ]
        )
    writer.writerows(rows)
    return stream.getvalue()


def stub_sectors(monkeypatch):
    from aperture.sectors import parse

    rows = parse(
        archive_csv(
            [
                [
                    "ABC",
                    "1",
                    "ABC Corporation",
                    "information_technology",
                    "2000-01-01",
                    "",
                    "2007-03-05",
                ],
                [
                    "NEW",
                    "2",
                    "NEW Corporation",
                    "industrials",
                    "2000-01-01",
                    "",
                    "2007-03-05",
                ],
            ]
        )
    )
    monkeypatch.setattr(
        "aperture.sectors.capture",
        lambda store, **kwargs: (
            rows,
            {
                "url": "https://example.com/fixture-sectors.csv",
                "captured_at": "2024-05-06T00:00:00+00:00",
                "sha256": "fixture-v1",
            },
        ),
    )
