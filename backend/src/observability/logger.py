import logging


def configure_logger() -> None:
	"""Configura todos os loggers e handlers da aplicação no nível INFO."""
	logging.basicConfig(level=logging.INFO)

	root_logger = logging.getLogger()
	root_logger.setLevel(logging.INFO)
	for handler in root_logger.handlers:
		handler.setLevel(logging.INFO)

	for logger in logging.Logger.manager.loggerDict.values():
		if isinstance(logger, logging.Logger):
			logger.setLevel(logging.INFO)
			for handler in logger.handlers:
				handler.setLevel(logging.INFO)
	logging.getLogger(__name__).info("Logger configured to INFO level.")
