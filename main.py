import keyboard
import os
import time
import pyautogui
import google.generativeai as genai
from dotenv import load_dotenv
import json
from PIL import Image

def configure_gemini():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("Missing API_KEY in environment variables.")
    genai.configure(api_key=api_key)

def detect_clickable_elements(image_path, min_width=50, max_width=400, min_height=20, max_height=200):
    # CV2 logic removed; return empty list
    return []

def send_prompt_to_gemini(prompt, image_path=None, elements=None, contents=None):
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    # If contents is provided (for regional grid logic), use it directly
    if contents is not None:
        response = model.generate_content(contents)
        return response.text.strip() if hasattr(response, 'text') else str(response).strip()
    # Otherwise, use the old logic
    if elements:
        prompt = f"{prompt}\n\nClickable elements metadata (JSON):\n{json.dumps(elements, indent=2)}"
    contents = [{"text": prompt}]
    if image_path:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        contents.append({"inline_data": {"mime_type": "image/png", "data": img_bytes}})
    response = model.generate_content(contents)
    return response.text.strip() if hasattr(response, 'text') else str(response).strip()

def take_screenshot():
    screenshot = pyautogui.screenshot()
    path = "screen.png"
    screenshot.save(path)
    return path

def split_screenshot_into_grid(image_path, rows=3, cols=4):
    from PIL import Image
    img = Image.open(image_path)
    img_w, img_h = img.size
    region_w = img_w // cols
    region_h = img_h // rows
    region_paths = []
    region_dir = "region_ss"
    if not os.path.exists(region_dir):
        os.makedirs(region_dir)
    for r in range(rows):
        for c in range(cols):
            left = c * region_w
            upper = r * region_h
            right = (c + 1) * region_w if c < cols - 1 else img_w
            lower = (r + 1) * region_h if r < rows - 1 else img_h
            region = img.crop((left, upper, right, lower))
            region_path = os.path.join(region_dir, f"region_{r}_{c}.png")
            region.save(region_path)
            region_paths.append({
                "row": r,
                "col": c,
                "path": region_path,
                "left": left,
                "top": upper,
                "width": right - left,
                "height": lower - upper
            })
    return region_paths

def parse_actions_from_gemini(response):
    try:
        resp = response.strip()
        if resp.startswith("```"):
            resp = resp.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(resp)
    except Exception as e:
        print(f"[!] Failed to parse Gemini response: {e}")
        return []

def perform_mouse_action(action):
    # Region-based click logic
    if "region_row" in action and "region_col" in action:
        region_row = action["region_row"]
        region_col = action["region_col"]
        x = action.get("x")
        y = action.get("y")
        if x is None or y is None:
            print("[!] Invalid mouse action coordinates.")
            return
        screen_w, screen_h = pyautogui.size()
        region_w = screen_w // 4
        region_h = screen_h // 3
        abs_x = region_col * region_w + x
        abs_y = region_row * region_h + y
        print(f"[Click] Gemini: region ({region_row},{region_col}), rel ({x},{y}) → abs ({abs_x},{abs_y})")
        pyautogui.moveTo(abs_x, abs_y)
        pyautogui.click()
        return

    # Fallback: old logic
    x = action.get("x")
    y = action.get("y")
    if x is None or y is None:
        print("[!] Invalid mouse action coordinates.")
        return

    screen_w, screen_h = pyautogui.size()
    screenshot = pyautogui.screenshot()
    img_w, img_h = screenshot.size

    if screen_w == img_w and screen_h == img_h:
        # No scaling needed
        print(f"[Click] Gemini: ({x}, {y}) [no scaling]")
        pyautogui.moveTo(x, y)
        pyautogui.click()
    else:
        # Calculate scale factors
        scale_x = screen_w / img_w
        scale_y = screen_h / img_h
        true_x = int(x * scale_x)
        true_y = int(y * scale_y)
        print(f"[Click] Gemini: ({x}, {y}) | Screenshot size: {img_w}x{img_h} | Screen size: {screen_w}x{screen_h} → Scaled: ({true_x}, {true_y})")
        pyautogui.moveTo(true_x, true_y)
        pyautogui.click()

def perform_keyboard_action(action):
    key = action.get("key")
    if key:
        key_map = {
            "win": "winleft", "windows": "winleft",
            "ctrl": "ctrl", "alt": "alt", "shift": "shift",
            "enter": "enter", "esc": "esc", "tab": "tab", "space": "space",
        }
        key_to_press = key_map.get(key.lower(), key)
        print(f"[Key Press] {key_to_press}")
        pyautogui.press(key_to_press)
    text = action.get("text")
    if text:
        print(f"[Typing] {text}")
        pyautogui.write(text)

def perform_actions(actions):
    for action in actions:
        if action.get("type") == "click":
            perform_mouse_action(action)
        elif action.get("type") in ["key", "type"]:
            perform_keyboard_action(action)
        time.sleep(0.5)

def main():
    def clear_mini_ss():
        mini_ss_dir = "mini_ss"
        if os.path.exists(mini_ss_dir):
            for f in os.listdir(mini_ss_dir):
                try:
                    os.remove(os.path.join(mini_ss_dir, f))
                except Exception as e:
                    print(f"[!] Could not delete {f}: {e}")
            print("[Mini screenshots cleared]")
        else:
            print("[mini_ss folder does not exist]")

    keyboard.add_hotkey('ctrl+shift+del', clear_mini_ss)
    configure_gemini()
    task = input("Describe the task Gemini should perform: ")
    screen_width, screen_height = pyautogui.size()
    stop_flag = {"stop": False}

    def stop_loop():
        stop_flag["stop"] = True
        print("\n[Stopped by user]")

    keyboard.add_hotkey('ctrl+esc', stop_loop)

    previous_action = None
    repeat_count = 0
    max_repeats = 3

    while not stop_flag["stop"]:
        screenshot_path = take_screenshot()
        region_grid = split_screenshot_into_grid(screenshot_path, rows=3, cols=4)

        # Compose region info for prompt
        region_info = [
            {"row": r["row"], "col": r["col"], "path": r["path"]} for r in region_grid
        ]

        prev_actions_text = f"\nPrevious action: {json.dumps(previous_action, indent=2)} | Repeat count: {repeat_count}" if previous_action else ""
        prompt = (
            f"You are controlling my Windows PC. Here is a screenshot. Screen resolution: {screen_width}x{screen_height}. "
            f"Task: {task}. "
            "The screen is divided into a 3x4 grid (3 rows, 4 columns). Each region is provided as a separate image. "
            "You will be given the full screenshot and the regional screenshots. "
            "Prefer keyboard shortcuts or typing over mouse clicks whenever possible, but use mouse clicks if there is no reliable keyboard or typing option. "
            "To click, return a JSON array of actions. For a click, specify the region (row, col) and the coordinates (x, y) relative to the top-left of that region. "
            "Example: {\"type\": \"click\", \"region_row\": 1, \"region_col\": 2, \"x\": 50, \"y\": 30, \"description\": \"what you are clicking\"}. "
            "Other actions: {\"type\": \"key\", \"key\": \"win\"} or {\"type\": \"type\", \"text\": \"your_text\"}. "
            "If task is already complete, return []. Do NOT return anything else. "
            "If previous actions did not work, try a different, creative approach."
            f"\nGrid region info: {json.dumps(region_info, indent=2)}"
            f"{prev_actions_text}"
        )

        # Add all region images to Gemini
        contents = [{"text": prompt}]
        with open(screenshot_path, "rb") as f:
            img_bytes = f.read()
        contents.append({"inline_data": {"mime_type": "image/png", "data": img_bytes}})
        for region in region_grid:
            with open(region["path"], "rb") as f:
                region_bytes = f.read()
            contents.append({"inline_data": {"mime_type": "image/png", "data": region_bytes}})

        response = send_prompt_to_gemini(prompt=None, image_path=None, elements=None, contents=contents)
        print("\nGemini response:", response)
        actions = parse_actions_from_gemini(response)

        # Only count as repeated if the same action is returned consecutively
        if actions == previous_action and actions:
            repeat_count += 1
            print(f"[!] Gemini repeated the same actions ({repeat_count} times). Asking for a different approach...")
            if repeat_count > max_repeats:
                print("[!] Too many repeated attempts. Stopping.")
                break
            continue
        else:
            repeat_count = 0

        previous_action = actions
        if not actions:
            print("✅ No more actions needed. Task complete.")
            break

        perform_actions(actions)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
