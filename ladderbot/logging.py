# Copyright (c) 2021 Jasper Harrison. This file is licensed under the terms of the Apache license, version 2.0. #
import logging
import logging.handlers
import pathlib

file = pathlib.Path(__file__).parent.joinpath('logs/ladderbot.log')

handler = logging.handlers.RotatingFileHandler(
    file, maxBytes=1000 * 1000 * 2,
    backupCount=10, encoding='utf-8'
)
handler.setFormatter(
    logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
)
stream = logging.StreamHandler()
stream.setFormatter(
    logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
)

logger = logging.getLogger('polyladderbot')
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(stream)
