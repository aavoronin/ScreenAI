import subprocess
import time


def start_wsl_server():
    """Start the AI server inside WSL from Windows."""
    wsl_distro = "Ubuntu"
    wsl_user = "av"
    wsl_workdir = "/home/av/ai-server"
    conda_env = "AI-Server"
    conda_prefix = f"/home/{wsl_user}/miniconda3/envs/{conda_env}"

    # Kill any existing process on port 8000 to prevent "address already in use"
    kill_cmd = "fuser -k 8000/tcp 2>/dev/null || true"

    # Force LD_LIBRARY_PATH to prioritize Conda and PyTorch's bundled CUDA 12.8 libraries.
    # This prevents the system from loading an older libcudart.so.12 from /usr/lib which causes
    # the "undefined symbol: cudaGetDriverEntryPointByVersion" error.
    env_setup = (
        f"export LD_LIBRARY_PATH={conda_prefix}/lib:"
        f"{conda_prefix}/lib/python3.10/site-packages/nvidia/cuda_runtime/lib:"
        f"$LD_LIBRARY_PATH"
    )

    start_cmd = f"{env_setup} && conda activate {conda_env} && cd {wsl_workdir} && python main.py"

    command = [
        "wsl",
        "-d", wsl_distro,
        "-u", wsl_user,
        "--",
        "bash", "-ic", f"{kill_cmd} && {start_cmd}"
    ]

    print("Starting AI server in WSL (Ubuntu)...")
    print(f"Working directory: {wsl_workdir}")
    print(f"Conda environment: {conda_env}")
    print("Access the server in your browser at: http://localhost:8000 or http://127.0.0.1:8000")

    try:
        subprocess.Popen(command)
        print("Server started in background. Control released.")
        time.sleep(3)
    except Exception as e:
        print(f"Failed to start server: {e}")


def stop_wsl_server():
    """Stop the AI server inside WSL."""
    wsl_distro = "Ubuntu"
    wsl_user = "av"

    command = [
        "wsl",
        "-d", wsl_distro,
        "-u", wsl_user,
        "--",
        "bash", "-c", "fuser -k 8000/tcp 2>/dev/null || true"
    ]

    print("Stopping AI server in WSL (Ubuntu)...")
    try:
        subprocess.run(command, check=True)
        print("Server stopped successfully.")
    except Exception as e:
        print(f"Failed to stop server: {e}")