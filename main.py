import time
from datetime import datetime, timedelta
from Navigators.HirifyNavigator import HirifyNavigator
from Navigators.LinkedInNavigator import LinkedInNavigator
from Navigators.PeriodSummary import PeriodSummary
from Screen.HirifyScreenParser import HirifyScreenParser
from ai_clients.start_server import start_wsl_server, stop_wsl_server
from project_to_file.project_to_file import project_to_file_main
import torch
from llama_cpp import llama_supports_gpu_offload
from Screen.TestScreenshots import test_screenshots
from cfg.cfg import Config


def verify_gpu():
    print("=" * 60)
    print("🔌 GPU SYSTEM CHECK")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Active GPU: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
        print('llama GPU Offload Supported:', llama_supports_gpu_offload())
    else:
        print("⚠️ WARNING: CUDA is not available. Models will run on CPU.")
    print("=" * 60)


if __name__ == "__main__":
    # time.sleep(3600 * 4)
    config = Config()
    OMNIPARSER_REPO_PATH = config.get_path('omniparser_repo_path')
    project_to_file_main()
    # verify_gpu()
    # test_screenshots()
    nv1 = LinkedInNavigator(OMNIPARSER_REPO_PATH)
    # nv1.group_vacancies()
    nv2 = HirifyNavigator(OMNIPARSER_REPO_PATH)
    # nv2.group_vacancies()

    # Generate period summary for the last 14 days
    period_end = datetime.now()
    period_start = period_end - timedelta(days=14)
    summary_output_path = config.get_path('summary_output_path')

    if summary_output_path:
        PeriodSummary.generate_period_summary(
            navigators=[nv1, nv2],
            output_folder=summary_output_path,
            period_start=period_start,
            period_end=period_end
        )
    else:
        print("⚠️ summary_output_path not found in config.")

    if False:
        for nv in [nv1, nv2]:
            nv.analyze_collected()
    while True:
        for nv in [nv1, nv1, nv1, nv2]:
            for _ in range(1):
                nv.AI_estimate_collected()
        for nv in [nv1, nv1, nv1, nv2]:
            nv.run_on_urls(1)
