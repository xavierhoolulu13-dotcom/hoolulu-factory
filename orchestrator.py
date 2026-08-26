import os
import datetime
import sqlite3
import sys


BASE = os.path.expanduser("~/hoolulu-factory")

if BASE not in sys.path:
    sys.path.insert(0, BASE)


DB = os.path.expanduser("~/hoolulu-factory/data/hoolulu.db")

def log(message):

    os.makedirs(
        f"{BASE}/logs",
        exist_ok=True
    )

    with open(
        f"{BASE}/logs/system.log",
        "a"
    ) as f:
        f.write(
            f"{datetime.datetime.now()} | {message}\n"
        )


from agents.scoring import score_lead
from agents.echo.echo import enrich
from agents.outreach.outreach import create_outreach
from agents.closer.closer import qualify


def fetch_leads(status):

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    c = conn.cursor()

    c.execute(
        """
        SELECT *
        FROM leads
        WHERE status = ?
        """,
        (status,)
    )

    rows = [
        dict(row)
        for row in c.fetchall()
    ]

    conn.close()

    return rows


def update_lead(lead_id, fields):

    conn = sqlite3.connect(DB)

    c = conn.cursor()


    sets = ", ".join(
        [
            f"{key} = ?"
            for key in fields.keys()
        ]
    )


    values = list(fields.values())

    values.append(lead_id)


    c.execute(
        f"""
        UPDATE leads
        SET {sets}
        WHERE id = ?
        """,
        values
    )


    conn.commit()
    conn.close()



def run_scoring():

    leads = fetch_leads(
        "NEW"
    )

    results = []


    for lead in leads:

        updated = score_lead(
            lead
        )

        update_lead(
            lead["id"],
            updated
        )

        results.append(updated)


    return {
        "agent": "Scoring",
        "processed": len(results),
        "results": results
    }



def run_enrichment():

    leads = fetch_leads(
        "SCORED"
    )

    results = []


    for lead in leads:

        updated = enrich(
            lead
        )

        update_lead(
            lead["id"],
            updated
        )

        results.append(updated)


    return {
        "agent": "Enrichment",
        "processed": len(results),
        "results": results
    }



def run_outreach():

    leads = fetch_leads(
        "OUTREACH_READY"
    )


    results = []


    for lead in leads:

        updated = create_outreach(
            lead
        )


        update_lead(
            lead["id"],
            {
                "outreach_status": updated.get(
                    "outreach_status",
                    "READY"
                ),

                "message": updated.get(
                    "message",
                    ""
                ),

                "notes": updated.get(
                    "notes",
                    ""
                )
            }
        )


        results.append(
            lead["business"]
        )


    return {
        "agent": "Outreach",
        "processed": len(results),
        "results": results
    }



def run_closer():

    from agents.closer.closer import process_closer

    result = process_closer()

    return {
        "agent": "Closer Cass",
        "processed": result["queue"],
        "results": result["results"]
    }


def run(task):

    task = task.lower()

    log(
        f"Received task: {task}"
    )


    if "score" in task:
        return run_scoring()


    if "enrich" in task:
        return run_enrichment()


    if "outreach" in task:
        return run_outreach()


    if "closer" in task or "close" in task:
        return run_closer()


    if "intel" in task:

        from agents.intelligence.intelligence_agent import run_batch

        return run_batch()


    return {
        "status": "unknown",
        "task": task
    }



if __name__ == "__main__":

    import sys

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "score"

    print(run(task))
