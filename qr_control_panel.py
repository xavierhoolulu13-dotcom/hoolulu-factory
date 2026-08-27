#!/usr/bin/env python3

from flask import Flask
import service_manager

app = Flask(__name__)

@app.route("/trigger/<service>")
def trigger(service):
    service_manager.start_service(service)
    return f"Triggered {service}", 200

@app.route("/stop/<service>")
def stop(service):
    service_manager.stop_service(service)
    return f"Stopped {service}", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
