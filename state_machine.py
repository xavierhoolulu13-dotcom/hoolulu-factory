VALID_STATES = [
    "NEW",
    "SCORED",
    "ENRICHING",
    "READY_FOR_OUTREACH",
    "CONTACTED",
    "REPLIED",
    "BOOKED",
    "CLIENT",
    "ARCHIVED"
]


def update_state(current, new):

    if new not in VALID_STATES:
        return False

    print(f"STATE: {current} → {new}")

    return new


if __name__ == "__main__":

    update_state(
        "NEW",
        "SCORED"
    )
