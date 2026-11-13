"""Server development (laptop). Jangan dipakai untuk diakses orang lain; pakai serve.py."""
from crm import create_app
from crm.sla_job import start_background

app = create_app()

if __name__ == "__main__":
    start_background(app)
    app.run(host="127.0.0.1", port=5100, debug=True, use_reloader=False)
