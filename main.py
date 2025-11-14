import logging

from config.settings import cf
from src.processors.processor import TestProcessor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    processor = TestProcessor(api_url=cf.API_AGENT_AI, iou_threshold=0.3)
    # processor = TestProcessor(api_url=cf.API_AGENT_AI, iou_threshold=0.01, debug=True, batch_debug='Linfox_Viet_Nam_USEPHONE_20251113_152617')
    processor.run()
