
import random
import string
from flask import Flask, request, jsonify
import os
import base64
import json
import requests
import tempfile
import time
from PIL import Image
import numpy as np
from io import BytesIO
from rembg import remove

app = Flask(__name__)
sd_url = 'http://127.0.0.1:7860'
gen_assets_dir = os.path.join(tempfile.gettempdir(), "after_ai_assets")
os.makedirs(gen_assets_dir, exist_ok=True)


@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "ok": True,
        "service": "After-AI local gateway",
        "health": "/health",
        "routes": [
            "/ai/refine_prompt",
            "/generate/image",
            "/generate/audio",
            "/api/remove-bg"
        ]
    })


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return ("", 204)


def _decode_data_url_or_base64(value):
    if not value:
        return None
    if "," in value:
        value = value.split(",", 1)[1]
    return base64.b64decode(value)


def _save_bytes_to_temp(content_bytes, suffix):
    filename = f"asset_{int(time.time())}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}{suffix}"
    target_path = os.path.join(gen_assets_dir, filename)
    with open(target_path, "wb") as f:
        f.write(content_bytes)
    return target_path


def _download_to_temp(url, suffix_guess=".bin"):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    suffix = suffix_guess
    if "image/png" in content_type:
        suffix = ".png"
    elif "image/jpeg" in content_type:
        suffix = ".jpg"
    elif "audio/mpeg" in content_type:
        suffix = ".mp3"
    elif "audio/wav" in content_type:
        suffix = ".wav"
    return _save_bytes_to_temp(response.content, suffix)


def _gemini_refine_prompt(text, target):
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        return f"[fallback refined {target}] {text}"

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-pro:generateContent?key=" + gemini_api_key
    )

    if target == "audio":
        instruction = (
            "You are a music prompt engineer. Rewrite the user's intent into concise tags and style "
            "descriptions suitable for AI music generation. Return plain text only."
        )
    else:
        instruction = (
            "You are a cinematic image prompt engineer. Rewrite the user's intent into a concise, "
            "high-quality prompt suitable for image generation. Return plain text only."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{instruction}\n\nUser input:\n{text}"
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return f"[fallback refined {target}] {text}"
        parts = candidates[0].get("content", {}).get("parts", [])
        refined = "".join(p.get("text", "") for p in parts).strip()
        return refined if refined else f"[fallback refined {target}] {text}"
    except Exception as ex:
        print("Gemini refine failed:", str(ex))
        return f"[fallback refined {target}] {text}"


def _generate_image_with_sd(prompt):
    payload = {
        "prompt": prompt,
        "width": 1024,
        "height": 576,
        "steps": 24,
        "cfg_scale": 7
    }
    url = f'{sd_url}/sdapi/v1/txt2img'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=payload, timeout=240)
    response.raise_for_status()
    response_data = response.json()
    if "images" not in response_data or not response_data["images"]:
        raise RuntimeError("SD returned empty image list")
    image_data = base64.b64decode(response_data["images"][0])
    local_path = _save_bytes_to_temp(image_data, ".png")
    return {
        "provider": "sd",
        "local_path": local_path,
        "preview_url": "file:///" + local_path.replace("\\", "/")
    }


def _generate_image_with_mj_proxy(prompt):
    mj_base = os.getenv("MJ_PROXY_BASE_URL", "").strip()
    mj_api_key = os.getenv("MJ_PROXY_API_KEY", "").strip()
    if not mj_base:
        raise RuntimeError("MJ_PROXY_BASE_URL not configured")

    imagine_url = mj_base.rstrip("/") + "/imagine"
    payload = {"prompt": prompt}
    headers = {"Content-Type": "application/json"}
    if mj_api_key:
        headers["Authorization"] = f"Bearer {mj_api_key}"

    task_resp = requests.post(imagine_url, headers=headers, json=payload, timeout=120)
    task_resp.raise_for_status()
    task_data = task_resp.json()
    task_id = task_data.get("task_id") or task_data.get("id")
    if not task_id:
        raise RuntimeError("MJ proxy did not return task id")

    status_url = mj_base.rstrip("/") + f"/tasks/{task_id}"
    image_url = None
    for _ in range(60):
        time.sleep(2)
        st_resp = requests.get(status_url, headers=headers, timeout=60)
        st_resp.raise_for_status()
        st_data = st_resp.json()
        state = (st_data.get("status") or "").lower()
        if state in ["success", "done", "completed"]:
            image_url = st_data.get("image_url") or st_data.get("url")
            break
        if state in ["failed", "error", "canceled"]:
            raise RuntimeError(f"MJ task failed: {st_data}")

    if not image_url:
        raise RuntimeError("MJ task timeout or missing image url")

    local_path = _download_to_temp(image_url, ".png")
    return {
        "provider": "mj",
        "local_path": local_path,
        "preview_url": image_url
    }


def _generate_audio_with_suno_proxy(prompt, duration):
    suno_base = os.getenv("SUNO_PROXY_BASE_URL", "").strip()
    suno_api_key = os.getenv("SUNO_PROXY_API_KEY", "").strip()
    if not suno_base:
        raise RuntimeError("SUNO_PROXY_BASE_URL not configured")

    create_url = suno_base.rstrip("/") + "/generate"
    payload = {
        "prompt": prompt,
        "duration": duration
    }
    headers = {"Content-Type": "application/json"}
    if suno_api_key:
        headers["Authorization"] = f"Bearer {suno_api_key}"

    task_resp = requests.post(create_url, headers=headers, json=payload, timeout=120)
    task_resp.raise_for_status()
    task_data = task_resp.json()
    task_id = task_data.get("task_id") or task_data.get("id")
    if not task_id:
        raise RuntimeError("Suno proxy did not return task id")

    status_url = suno_base.rstrip("/") + f"/tasks/{task_id}"
    audio_url = None
    for _ in range(90):
        time.sleep(2)
        st_resp = requests.get(status_url, headers=headers, timeout=60)
        st_resp.raise_for_status()
        st_data = st_resp.json()
        state = (st_data.get("status") or "").lower()
        if state in ["success", "done", "completed"]:
            audio_url = st_data.get("audio_url") or st_data.get("url")
            break
        if state in ["failed", "error", "canceled"]:
            raise RuntimeError(f"Suno task failed: {st_data}")

    if not audio_url:
        raise RuntimeError("Suno task timeout or missing audio url")

    local_path = _download_to_temp(audio_url, ".mp3")
    return {
        "provider": "suno",
        "local_path": local_path
    }

@app.route('/change_url', methods=['POST'])
def change_sd_url():
    # Get the new sd_url from the request payload
    payload = request.get_json()
    print('Payload:', payload)
    new_sd_url = payload.get('sd_url', None)
    print('New sd_url:', new_sd_url)

    if new_sd_url is None:
        return "Error: 'sd_url' not found in the request payload", 400

    # Update the global sd_url variable with the new value
    global sd_url
    sd_url = new_sd_url
    print(f"sd_url changed to {sd_url}")
    return "sd_url changed successfully"


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"ok": True, "sd_url": sd_url})


@app.route('/ai/refine_prompt', methods=['POST'])
def refine_prompt():
    payload = request.get_json() or {}
    text = (payload.get("text") or "").strip()
    target = (payload.get("target") or "image").strip().lower()
    if not text:
        return jsonify({"error": "text is required"}), 400
    refined = _gemini_refine_prompt(text, target)
    return jsonify({"prompt": refined, "target": target})


@app.route('/generate/image', methods=['POST'])
def generate_image():
    payload = request.get_json() or {}
    provider = (payload.get("provider") or "mj").strip().lower()
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    try:
        if provider == "sd":
            result = _generate_image_with_sd(prompt)
        elif provider == "mj":
            result = _generate_image_with_mj_proxy(prompt)
        else:
            return jsonify({"error": f"unsupported image provider: {provider}"}), 400
        return jsonify(result)
    except Exception as ex:
        print("generate/image failed:", str(ex))
        return jsonify({"error": str(ex)}), 500


@app.route('/generate/audio', methods=['POST'])
def generate_audio():
    payload = request.get_json() or {}
    provider = (payload.get("provider") or "suno").strip().lower()
    prompt = (payload.get("prompt") or "").strip()
    duration = int(payload.get("duration") or 30)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if provider != "suno":
        return jsonify({"error": f"unsupported audio provider: {provider}"}), 400

    try:
        refined_prompt = _gemini_refine_prompt(prompt, "audio")
        result = _generate_audio_with_suno_proxy(refined_prompt, duration)
        result["prompt"] = refined_prompt
        return jsonify(result)
    except Exception as ex:
        print("generate/audio failed:", str(ex))
        return jsonify({"error": str(ex)}), 500


@app.route('/api/remove-bg', methods=['POST'])
def remove_bg():
    payload = request.get_json() or {}
    image_b64 = payload.get("image_base64")
    if not image_b64:
        return jsonify({"error": "image_base64 is required"}), 400

    try:
        input_bytes = _decode_data_url_or_base64(image_b64)
        output_bytes = remove(input_bytes)
        local_path = _save_bytes_to_temp(output_bytes, ".png")
        return jsonify({
            "local_path": local_path,
            "preview_url": "file:///" + local_path.replace("\\", "/")
        })
    except Exception as ex:
        print("remove-bg failed:", str(ex))
        return jsonify({"error": str(ex)}), 500


@app.route('/text2image', methods=['POST'])
def process_image():
    # Get the payload from the CEP extension
    payload = request.get_json()
    # Send the payload to the external API
    url = f'{sd_url}/sdapi/v1/txt2img'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    # Parse the 'info' string into a Python dictionary
    info = json.loads(response_data.get('info', '{}'))
    print('Response Data:', response_data)
    # Extract the seed value from the 'info' key
    seed = info.get('seed', None)

    # Save the image to the temp directory
    try:
        image_data = base64.b64decode(response_data['images'][0])
    except KeyError:
        print("Error: 'images' key not found in response_data")
        # You can return an error message or handle the situation as appropriate
        return "Error: 'images' key not found in response_data", 400

    temp_dir = tempfile.gettempdir()

    # Use the seed value in the file name
    image_path = os.path.join(temp_dir, f'image_{seed}.png') if seed is not None else os.path.join(temp_dir, f'image_{int(time.time())}.png')

    with open(image_path, 'wb') as f:
        f.write(image_data)

    # Create a JSON object containing the path to the saved image and the seed value
    response_json = {'imagePath': image_path, 'seed': seed}
    

    # Serialize the JSON object to a string
    response_str = json.dumps(response_json)
    print('Response String:', response_str)
    # Return the JSON string as part of the HTTP response
    return response_str

@app.route('/image2image', methods=['POST'])
def process_image2():
    # Get the payload from the CEP extension
    payload = request.get_json()
    # Extract the frame path from the payload
    frame_path = payload['images']['path']

    # Update the payload to have the b64 image instead of the path
    with open(frame_path, 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    payload['init_images'] = [encoded_image]

    # Check if 'mask' is in the payload
    if 'mask' in payload:
        # Extract the mask path from the payload
        mask_path = payload['mask']['path']

        # Update the payload to have the b64 mask instead of the path
        with open(mask_path, 'rb') as mask_file:
            encoded_mask = base64.b64encode(mask_file.read()).decode('utf-8')
        payload['mask'] = encoded_mask

    # Send the payload to the external API
    url = f'{sd_url}/sdapi/v1/img2img'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    # Parse the 'info' string into a Python dictionary
    info = json.loads(response_data.get('info', '{}'))
    print('Response Data:', response_data)
    # Extract the seed value from the 'info' key
    seed = info.get('seed', None)

    # Save the image to the temp directory
    try:
        image_data = base64.b64decode(response_data['images'][0])
    except KeyError:
        print("Error: 'images' key not found in response_data")
        # You can return an error message or handle the situation as appropriate
        return "Error: 'images' key not found in response_data", 400

    temp_dir = tempfile.gettempdir()

    # Use the seed value in the file name
   # Generate a random suffix for uniqueness
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

# Use the seed value in the file name
    image_path = os.path.join(temp_dir, f'image_{suffix}_{seed}.png') if seed is not None else os.path.join(temp_dir, f'image_{int(time.time())}_{suffix}.png')
    with open(image_path, 'wb') as f:
        f.write(image_data)

    # Create a JSON object containing the path to the saved image and the seed value
    response_json = {'imagePath': image_path, 'seed': seed}
    

    # Serialize the JSON object to a string
    response_str = json.dumps(response_json)
    print('Response String:', response_str)
    # Return the JSON string as part of the HTTP response
    return response_str


@app.route("/swapModel", methods=["POST"])
def swapModel():
    payload = request.get_json()
    url = f'{sd_url}/sdapi/v1/options'
    response = requests.post(url, json=payload)
    return jsonify(response.json())

@app.route("/get_sd_models", methods=["POST"])
def get_sd_models():
    url = f'{sd_url}/sdapi/v1/sd-models'
    print(url)
    response = requests.get(url)
    print(response.json())
    return jsonify(response.json())

@app.route("/controlnet/model_list", methods=["POST"])
def controlnet_model():
    url = f'{sd_url}/controlnet/model_list'
    response = requests.get(url)
    return jsonify(response.json())

@app.route("/controlnet/module_list", methods=["POST"])
def controlnet_module():
    url = f'{sd_url}/controlnet/module_list'
    response = requests.get(url)
    return jsonify(response.json())

@app.route('/create_grid', methods=['POST'])
def create_grid():
    # Get the payload from the request
    payload = request.get_json()
    print(payload)
    # Get images from payload
    images_data = payload.get('images', None)

    if images_data is None:
        return jsonify({"error": "Missing 'images' key in the request payload"}), 400

    # Get dimensions
    tile_height = payload['tilegHeight']
    tile_width = payload['tilegWidth']
    grid_height = payload['maxgHeight']
    grid_width = payload['maxgWidth']

    # Create a blank canvas for the grid
    grid_image = Image.new('RGBA', (grid_width, grid_height))

    # Process images
    for img in images_data:
        # Decode base64 image
        image_data = img['url'].split(",")[1]
        img_decoded = Image.open(BytesIO(base64.b64decode(image_data)))

        # Calculate the aspect ratio
        aspect_ratio = img_decoded.width / img_decoded.height
        new_height = tile_height
        new_width = tile_width

        # Adjust width or height based on the original image's aspect ratio
        if aspect_ratio > 1:
            # Image is wide
            new_height = tile_width // aspect_ratio
        elif aspect_ratio < 1:
            # Image is tall
            new_width = tile_height * aspect_ratio

        # Resize the image while maintaining the aspect ratio
        img_resized = img_decoded.resize((int(new_width), int(new_height)))

        # Get position
        pos = img['position']

        # Calculate paste position so the image is centered within its tile
        paste_x = pos['x']*tile_width + (tile_width - new_width) // 2
        paste_y = pos['y']*tile_height + (tile_height - new_height) // 2

        # Paste image into the grid at the correct position
        grid_image.paste(img_resized, (int(paste_x), int(paste_y)))

    # Save the grid image to a temporary file
    with tempfile.NamedTemporaryFile(dir='/tmp', delete=False, suffix='.png') as f:
        grid_image.save(f.name, 'PNG')
        temp_file_name = f.name

    return jsonify({'message': 'Grid created successfully', 'file_path': temp_file_name})

if __name__ == '__main__':
    app.run(port=8000)
