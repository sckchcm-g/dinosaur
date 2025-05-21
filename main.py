import keyboard
import os
import time
import pyautogui
import google.generativeai as genai
from dotenv import load_dotenv
import json

def configure_gemini():
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("Missing API_KEY in environment variables.")
    genai.configure(api_key=api_key)

def send_prompt_to_gemini(prompt, image_path=None):
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
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
    x = action.get("x")
    y = action.get("y")
    if x is not None and y is not None:
        screen_w, screen_h = pyautogui.size()
        screenshot = pyautogui.screenshot()
        img_w, img_h = screenshot.size
        scale_x = screen_w / img_w
        scale_y = screen_h / img_h
        true_x = int(x * scale_x)
        true_y = int(y * scale_y)
        print(f"[Click] Gemini: ({x}, {y}) → Scaled: ({true_x}, {true_y})")
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
    configure_gemini()
    task = input("Describe the task Gemini should perform: ")
    screen_width, screen_height = pyautogui.size()
    stop_flag = {"stop": False}

    def stop_loop():
        stop_flag["stop"] = True
        print("\n[Stopped by user]")

    keyboard.add_hotkey('ctrl+esc', stop_loop)

    while not stop_flag["stop"]:
        screenshot_path = take_screenshot()
        prompt = (
            f"You are controlling my Windows PC. Here is a screenshot. Screen resolution: {screen_width}x{screen_height}. "
            f"Task: {task}. "
            "You must be extremely careful and thoughtful before performing any mouse click. "
            "Only use mouse clicks if there is no reliable keyboard or typing alternative. "
            "If you decide to click, explain in a 'description' field exactly what you are clicking and why, e.g. 'search bar in the middle of the screen'. "
            "Return a JSON array of actions. Each action must be one of: "
            "{\"type\": \"click\", \"x\": x, \"y\": y, \"description\": \"what you are clicking\"}, "
            "{\"type\": \"key\", \"key\": \"win\"}, or "
            "{\"type\": \"type\", \"text\": \"your_text\"}. "
            "If task is already complete, return []. Do NOT return anything else."
        )

        response = send_prompt_to_gemini(prompt, screenshot_path)
        print("\nGemini response:", response)
        actions = parse_actions_from_gemini(response)
        if not actions:
            print("✅ No more actions needed. Task complete.")
            break

        perform_actions(actions)
        time.sleep(1)

if __name__ == "__main__":
    main()
