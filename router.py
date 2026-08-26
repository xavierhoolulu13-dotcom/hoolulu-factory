def route(status):

    routes = {

        "NEW": "scoring",

        "SCORED": "echo",

        "ENRICHED": "outreach",

        "READY_FOR_OUTREACH": "outreach",

        "CONTACTED": "closer",

        "BOOKED": "delivery",

        "CLIENT": "reporting"

    }

    return routes.get(
        status,
        "human_review"
    )


if __name__ == "__main__":

    print(route("ENRICHED"))
