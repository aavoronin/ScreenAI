# 1. Clone the repository into a folder named "omniparser"
git clone https://github.com/microsoft/OmniParser.git omniparser

# 2. Install the core OmniParser dependencies into your .venv
pip install -r omniparser\requirements.txt

# 3. Install Hugging Face CLI (required to download the model weights)
pip install huggingface-hub

# 4. Create the weights directory
New-Item -ItemType Directory -Force -Path omniparser\weights

# 5. Download the YOLO detection model files
huggingface-cli download microsoft/OmniParser-v2.0 icon_detect/model.pt --local-dir omniparser\weights
huggingface-cli download microsoft/OmniParser-v2.0 icon_detect/model.yaml --local-dir omniparser\weights
huggingface-cli download microsoft/OmniParser-v2.0 icon_detect/train_args.yaml --local-dir omniparser\weights

# 6. Download the Florence-2 caption model files
huggingface-cli download microsoft/OmniParser-v2.0 icon_caption/config.json --local-dir omniparser\weights
huggingface-cli download microsoft/OmniParser-v2.0 icon_caption/generation_config.json --local-dir omniparser\weights
huggingface-cli download microsoft/OmniParser-v2.0 icon_caption/model.safetensors --local-dir omniparser\weights

# 7. Rename the caption folder to match what the code expects
# Rename-Item -Path omniparser\weights\icon_caption -NewName icon_caption_florence


# Download all model weights into your weights folder in one go
hf download microsoft/OmniParser-v2.0 --local-dir omniparser\weights

pip install opencv-python Pillow

pip uninstall -y torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

pip uninstall -y paddleocr paddlepaddle
pip install paddleocr==2.7.3 paddlepaddle-gpu

pip install transformers==4.40.0

python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"


pip uninstall -y torch torchvision torchaudio paddlepaddle paddlepaddle-gpu paddleocr

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

pip install paddlepaddle==2.6.2 paddleocr==2.7.3

pip install transformers==4.46.3

pip install paddlepaddle paddleocr

python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

$env:CMAKE_ARGS="-DGGML_CUDA=on"
$env:FORCE_CMAKE=1
pip install llama-cpp-python --no-cache-dir

pip uninstall -y llama-cpp-python
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --no-cache-dir --force-reinstall