
import logging
import watchtower
# import faulthandler
import sys

# Configure logging
log_group_name = 'arb-opcodes'  

cloudwatch_handler = watchtower.CloudWatchLogHandler(log_group=log_group_name, 
                                                     send_interval=10,   # Send logs every 30 seconds
                                                     max_batch_count=1000, # Maximum number of logs per batch
                                                    )  # Optional stream name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        cloudwatch_handler,
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# # Redirect faulthandler output to the logger
# faulthandler.enable(file=sys.stderr)

# # Custom exception hook to log uncaught exceptions
# def log_exception(exc_type, exc_value, exc_traceback):
#     if issubclass(exc_type, KeyboardInterrupt):
#         sys.__excepthook__(exc_type, exc_value, exc_traceback)
#         return
#     logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# sys.excepthook = log_exception