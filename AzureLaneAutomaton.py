import time

import utility
from core.buttons import Button


CHECK_INTERVAL = 2.0
CLICK_COOLDOWN = 5.0


def main() -> None:
    print("Connecting to BlueStacks...")

    if not utility.adbAlive():
        raise RuntimeError("BlueStacks ADB is not responding.")

    print("ADB connected.")
    print("Watching for Redo Sortie...")
    print("Press Ctrl+C to stop.")

    last_click = 0.0

    while True:
        try:
            screen = utility.getScreenshot()

            if utility.exists(Button.REDO_SORTIE, screen):
                now = time.monotonic()

                if now - last_click >= CLICK_COOLDOWN:
                    print("Redo Sortie found!")

                    if utility.click(Button.REDO_SORTIE, screen):
                        print("Clicked Redo Sortie.")
                        last_click = now

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping.")
            break

        except Exception as exc:
            print(f"Error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()