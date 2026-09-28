import uvicorn

from dotenv import load_dotenv

from server import create_app


if __name__ == "__main__":
    load_dotenv()

    app = create_app()
    uvicorn.run(app=app, host="0.0.0.0", port=3000, log_level="info")
