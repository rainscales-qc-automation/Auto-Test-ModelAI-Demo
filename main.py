import logging

from config.settings import cf
from src.processors.processor import TestProcessor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    processor = TestProcessor(api_url=cf.API_STAGING, iou_threshold=0.3)
    processor.run()
