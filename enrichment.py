import csv
import os
from datetime import datetime


class EnrichmentEngine:
    def __init__(self):
        self.name = "Enrichment Echo"
        self.version = "0.1"

    def enrich_lead(self, lead):
        """
        Add intelligence fields to a lead.
        """
        lead["enriched"] = True
        lead["enriched_at"] = datetime.now().isoformat()

        if not lead.get("notes"):
            lead["notes"] = "Needs enrichment review"

        return lead


    def process_csv(self, input_file, output_file):
        results = []

        with open(input_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                results.append(self.enrich_lead(row))

        if results:
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=results[0].keys()
                )
                writer.writeheader()
                writer.writerows(results)

        print(f"ENRICHED {len(results)} LEADS")
        print(f"OUTPUT: {output_file}")


if __name__ == "__main__":
    engine = EnrichmentEngine()
    print(f"{engine.name} v{engine.version} READY")
