"""Открывает Streamlit-приложение в headless-браузере и будит его."""
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://mediaanalyzer-vpe39oggw3grdfonumcfhb.streamlit.app/"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"Открываю {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)

        # Ждём, пока либо появится кнопка пробуждения, либо приложение загрузится
        # (Streamlit рисует сайдбар/заголовок, когда проснулся)
        wake_button = None
        try:
            wake_button = page.wait_for_selector(
                "button:has-text('Yes, get this app back up')",
                timeout=15_000,
            )
        except PWTimeout:
            print("Кнопка пробуждения не появилась — возможно, приложение уже бодрое")


        if wake_button:
            print("Приложение спит — кликаю «Yes, get this app back up»")
            wake_button.click()
            # После клика ждём, пока Streamlit загрузит приложение
            try:
                page.wait_for_selector("h1:has-text('Media Analyzer')", timeout=90_000)
                print("Приложение проснулось")
            except PWTimeout:
                print("Кнопка нажата, но приложение не загрузилось за 90 с")
        else:
            # Убедимся, что приложение действительно бодрое, а не просто не показало кнопку
            try:
                page.wait_for_selector("h1:has-text('Media Analyzer')", timeout=30_000)
                print("Приложение бодрое (заголовок найден)")
            except PWTimeout:
                print("Заголовок не найден — возможно, приложение не загрузилось")

        # Скриншот для артефактов (пригодится для отладки)
        page.screenshot(path="wake.png", full_page=True)
        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())