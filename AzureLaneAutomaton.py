import utility


def main() -> None:
    print("Connecting to BlueStacks...")

    if not utility.adbAlive():
        raise RuntimeError("BlueStacks ADB is not responding.")

    screen = utility.getScreenshot()
    print(f"Screenshot: {screen.shape[1]}x{screen.shape[0]}")

    result = utility.identifyScreenDetails(screen)
    print(f"Screen: {result.screen.value} (confidence={result.score:.3f})")

    path = utility.saveDebug(screen, "startup")
    print(f"Saved startup screenshot to: {path}")


if __name__ == "__main__":
    main()
