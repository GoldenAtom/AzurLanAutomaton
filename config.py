from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5556"
PACKAGE_NAME = "com.YoStarEN.AzurLane"

EXPECTED_SCREEN_SIZE = (1920, 1080)

TEMPLATE_DIR = BASE_DIR / "templates"
BUTTON_TEMPLATE_DIR = TEMPLATE_DIR / "buttons"
SCREEN_TEMPLATE_DIR = TEMPLATE_DIR / "screens"
TIMER_TEMPLATE_DIR = TEMPLATE_DIR / "timer"
DEBUG_DIR = BASE_DIR / "debug"

DEFAULT_BUTTON_THRESHOLD = 0.90
DEFAULT_SCREEN_THRESHOLD = 0.72

# x1, y1, x2, y2. Tune once the exact battle-timer crop is settled.
BATTLE_TIMER_REGION = (1600, 20, 1820, 125)
