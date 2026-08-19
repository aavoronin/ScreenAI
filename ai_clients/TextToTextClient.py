import urllib.parse

from ai_clients.model_client_base import ModelClientBase


class TextToTextClient(ModelClientBase):
    """Client specialized for text-to-text generation requests."""

    def generate(self, model_id: str, prompt: str, max_new_tokens: int = None,
                 temperature: float = 0.7, model_limit_seconds: int = 60):
        """Send a text-to-text generation request to the server."""
        encoded_id = urllib.parse.quote(model_id, safe='')
        data = {
            "prompt": prompt,
            "temperature": temperature,
            "model_limit_seconds": model_limit_seconds
        }
        if max_new_tokens is not None:
            data["max_new_tokens"] = max_new_tokens
        return self._request("POST", f"/models/{encoded_id}/generate", data=data, timeout=model_limit_seconds)
