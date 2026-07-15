from Navigators.LinkedInNavigator import LinkedInNavigator
from project_to_file.project_to_file import project_to_file_main
import torch
from llama_cpp import llama_supports_gpu_offload

from Screen.TestScreenshots import test_screenshots, OMNIPARSER_REPO_PATH


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
    project_to_file_main()
    #verify_gpu()
    #test_screenshots()
    nv = LinkedInNavigator(OMNIPARSER_REPO_PATH)
    nv.run()