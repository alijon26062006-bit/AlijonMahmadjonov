"""Запуск панели: python run.py  (или uvicorn "run:app" --host 0.0.0.0 --port 8000 --proxy-headers)"""
import logging

import uvicorn

from app.main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
