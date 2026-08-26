import sys
import os

sys.path.append(
    os.path.expanduser("~/hoolulu-factory")
)

from core.database import get_new_leads, update_lead_score
from agents.qualification import qualify_lead
from agents.opportunity import create_opportunity
from agents.proposal import create_proposal
from core.opportunity_memory import save_opportunity
from core.proposal_memory import save_proposal


def run_pipeline():

    leads = get_new_leads()

    print(f"Found {len(leads)} NEW leads")

    for lead in leads:

        print("\nProcessing:", lead["business"])

        qualified = qualify_lead(lead)

        if qualified["status"] != "SCORED":
            continue

        opportunity = create_opportunity(
            qualified
        )

        save_opportunity(
            opportunity
        )

        proposal = create_proposal(
            opportunity
        )

        save_proposal(
            proposal
        )

        print("✅ Opportunity created")
        print("✅ Proposal created")


if __name__ == "__main__":
    run_pipeline()
