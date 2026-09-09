"""Start the coupon service: `python -m coupon_service [port]`."""

import os
import sys

from split_share_core.telemetry import configure_tracing


def main():
    if configure_tracing("split-share-coupons"):
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.mysqlclient import MySQLClientInstrumentor

        MySQLClientInstrumentor().instrument(enable_commenter=False, capture_parameters=False)
        from .app import app

        FlaskInstrumentor().instrument_app(app)
    else:
        from .app import app

    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("COUPON_SERVICE_PORT", "8001"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
