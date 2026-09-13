import logging
from dictation_tool.config import load_config
from dictation_tool.app import App


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    app = App(config)
    app.run()


if __name__ == "__main__":
    main()
