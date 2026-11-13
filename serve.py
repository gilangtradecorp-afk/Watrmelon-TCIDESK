"""Server produksi (PC Surabaya): waitress di semua interface, port 8000."""
from waitress import serve

from crm import create_app
from crm.sla_job import start_background

HOST, PORT = "0.0.0.0", 8000
app = create_app()

if __name__ == "__main__":
    start_background(app)
    print(f"Tradecorp CRM berjalan di http://{HOST}:{PORT}")
    serve(app, host=HOST, port=PORT, threads=8)
