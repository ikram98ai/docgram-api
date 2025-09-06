import logging, sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,          # Python 3.8+; forces basicConfig to override existing handlers
)

# Mirror handlers to uvicorn loggers (if your code or libraries use them)
root_handlers = logging.getLogger().handlers
logging.getLogger("mangum").handlers = root_handlers
