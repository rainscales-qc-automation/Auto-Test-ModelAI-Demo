import json
import multiprocessing as mp
from multiprocessing import Manager

from loguru import logger

from lib.until import send_video_to_ai, compare_ai_vs_ground_truth, export_report_to_excel


def function_process(task, log_pth):
    """
    Function to process each test video
    task: tuple (api_url, video_path, ground_truth_path, output_path)
    """
    api_url, video_path, ground_truth_path, output_path = task

    try:
        logger.info(f"=== STARTING AI MODEL TEST {video_path} ===")

        # Send video to AI
        ai_result = send_video_to_ai(api_url, video_path)
        if not ai_result:
            logger.error(f"Failed to get AI result for {video_path}")
            return {"status": "failed", "video": video_path, "error": "No AI result"}

        # Load ground truth
        with open(ground_truth_path, "r") as f:
            gt_json = json.load(f)

        # Compare results
        records = compare_ai_vs_ground_truth(ai_result, gt_json)

        # Export to Excel
        export_report_to_excel(records, output_path)

        logger.success(f"=== TEST COMPLETED SUCCESSFULLY for {video_path} ===")

        return {
            "status": "success",
            "video": video_path,
            "output": output_path,
            "records": len(records)
        }

    except Exception as e:
        logger.error(f"Error processing {video_path}: {str(e)}")
        return {
            "status": "failed",
            "video": video_path,
            "error": str(e)
        }


def worker(task, output, fn, log_pth, lock):
    result = fn(task, log_pth)
    with lock:
        output.append(result)
    with open(log_pth, 'a') as log_file:
        log_file.write(f"{result}\n")
    print(f"Appended result: {result}")


def process_pool_task(tasks, num_workers=4, output=None, function=None, log_pth=None):
    if output is None:
        raise ValueError("Output list must be provided")

    with Manager() as manager:
        output_list = manager.list(output)
        lock = manager.Lock()

        with mp.Pool(num_workers) as pool:
            pool.starmap(worker, [(task, output_list, function, log_pth, lock) for task in tasks])

        return list(output_list)



