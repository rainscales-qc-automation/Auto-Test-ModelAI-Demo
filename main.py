import os
from pathlib import Path

from loguru import logger

from lib.config import Config
from lib.parallel import process_pool_task, function_process

# def run_ai_model_test(api_url: str, video_path: str, ground_truth_path: str, output_path="ai_test_result.xlsx"):
#     from lib.until import send_video_to_ai, compare_ai_vs_ground_truth, export_report_to_excel
#     logger.info(f"=== STARTING AI MODEL TEST {video_path} ===")
#     ai_result = send_video_to_ai(api_url, video_path)
#     if not ai_result:
#         return None
#
#     with open(ground_truth_path, "r") as f:
#         gt_json = json.load(f)
#
#     records = compare_ai_vs_ground_truth(ai_result, gt_json)
#     export_report_to_excel(records, output_path)
#     logger.success("=== TEST COMPLETED SUCCESSFULLY ===")


def run_parallel_video_tests(api_url, video_dir, expected_result_dir, num_workers=4, log_pth="video_test.log"):
    """
    Run test parallel for all videos
    """
    tasks = []
    # Prepare tasks
    for video in os.listdir(video_dir):
        video_path = os.path.join(video_dir, video)
        video_name = Path(video).stem
        ground_truth_file = f"{video_name}.json"
        ground_truth_path = os.path.join(expected_result_dir, ground_truth_file)

        if not os.path.exists(ground_truth_path):
            logger.warning(f"Ground truth not found for {video}, skipping...")
            continue
        output_path = f"ai_test_result_{video_name}.xlsx"
        # Add task to list
        tasks.append((api_url, video_path, ground_truth_path, output_path))

    # Run parallel
    logger.info(f"Total tasks to process: {len(tasks)}")
    results = process_pool_task(
        tasks=tasks,
        num_workers=num_workers,
        output=[],
        function=function_process,
        log_pth=log_pth
    )
    return results


if __name__ == "__main__":
    cf = Config()
    video_dir = cf.get_folder_video()
    expected_result_dir = cf.get_folder_expected_result()

    # for video in os.listdir(video_dir):
    #     video_path = os.path.join(video_dir, video)
    #     video_name = Path(video).stem
    #     ground_truth_file = f"{video_name}.json"
    #     ground_truth_path = os.path.join(expected_result_dir, ground_truth_file)
    #
    #     run_ai_model_test(
    #         api_url=cf.API_STAGING,
    #         video_path=video_path,
    #         ground_truth_path=ground_truth_path,
    #         output_path="ai_test_result.xlsx"
    #     )

    results = run_parallel_video_tests(
        api_url=cf.API_STAGING,
        video_dir=cf.get_folder_video(),
        expected_result_dir=cf.get_folder_expected_result(),
        num_workers=4,
        log_pth="video_test.log"
    )

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    success_count = sum(1 for r in results if r.get("status") == "success")
    failed_count = sum(1 for r in results if r.get("status") == "failed")

    print(f"Total tests: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")

    if failed_count > 0:
        print("\nFailed tests:")
        for r in results:
            if r.get("status") == "failed":
                print(f"  - {r.get('video')}: {r.get('error')}")
