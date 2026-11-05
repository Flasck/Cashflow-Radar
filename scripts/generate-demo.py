import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fictional RUB payments")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/demo-transactions.csv")
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Output already exists; choose a new path to preserve the previous file."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["date", "amount", "direction", "category", "purpose"])
        count = 0
        for index in range(120):
            day = today - timedelta(days=119 - index)
            if day.weekday() < 5:
                amount = 18000 + day.weekday() * 1700 + index % 11 * 230
                writer.writerow(
                    [
                        day.isoformat(),
                        f"{amount}.00",
                        "inflow",
                        "Продажи",
                        "Учебный пример: вымышленное поступление",
                    ]
                )
                count += 1
            amount = 9000 + index % 7 * 410
            writer.writerow(
                [
                    day.isoformat(),
                    f"{amount}.00",
                    "outflow",
                    "Расходы",
                    "Учебный пример: вымышленная выплата",
                ]
            )
            count += 1
    print(f"Generated {count} fictional payments across 120 days: {args.output}")


if __name__ == "__main__":
    main()
