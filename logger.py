import datetime
import os

LOG=os.path.expanduser(
"~/hoolulu-factory/logs/system.log"
)


def write(event):

    with open(LOG,"a") as f:

        f.write(
        f"{datetime.datetime.now()} | {event}\n"
        )


if __name__=="__main__":

    write("Factory online")

    print("Logged")
