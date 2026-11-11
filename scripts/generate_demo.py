"""Regenerate the small, explicitly synthetic transaction fixture."""
import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "demo" / "transactions.csv"
START = date(2020, 1, 6)  # Monday; 52 complete Monday–Sunday weeks follow.

def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    fields = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    invoice = 100000
    with DEST.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for sku_index in range(22):
            sku = f"DEMO-{sku_index + 1:03d}"
            for week in range(52):
                # One deliberately intermittent SKU; all values are synthetic.
                if sku_index == 21 and week % 4 != 3:
                    continue
                invoice += 1
                seasonal = 1.0 + 0.18 * ((week % 13) / 12)
                trend = 1.0 + week * 0.003
                if sku_index == 21:
                    quantity = 1 + (week % 4)
                else:
                    quantity = max(1, round((5 + (sku_index * 3) % 27 + (week % 5)) * seasonal * trend))
                day_offset = 6 if week == 51 and sku_index == 0 else sku_index % 5
                day = START + timedelta(days=7 * week + day_offset)
                writer.writerow({"InvoiceNo": str(invoice), "StockCode": sku, "Description": f"Synthetic product {sku_index + 1:02d}", "Quantity": quantity, "InvoiceDate": f"{day.isoformat()} 10:15:00", "UnitPrice": round(2.5 + sku_index * 0.4, 2), "CustomerID": "", "Country": "Demo"})
        # Audit examples: a cancellation and a nonpositive return are expected to be excluded.
        for invoice_no, sku, qty, day in [("c-demo-1", "DEMO-001", -2, START + timedelta(days=40)), ("demo-return-1", "DEMO-002", -1, START + timedelta(days=43))]:
            writer.writerow({"InvoiceNo": invoice_no, "StockCode": sku, "Description": "Synthetic audit row", "Quantity": qty, "InvoiceDate": f"{day.isoformat()} 12:00:00", "UnitPrice": 5.0, "CustomerID": "", "Country": "Demo"})
    print(f"Wrote synthetic-only fixture: {DEST}")

if __name__ == "__main__":
    main()
