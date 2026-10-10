from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug must match app.debug, which the alert scheduler's reloader guard read at startup.
    app.run(host=app.config["SERVER_HOST"], port=app.config["SERVER_PORT"], debug=app.debug)
