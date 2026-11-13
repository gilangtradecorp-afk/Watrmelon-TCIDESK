import click


def register(app):
    @app.cli.command("sla-check")
    def sla_check():
        """Jalankan pemeriksaan SLA sekali."""
        from .sla_job import run_check
        with app.test_request_context():
            click.echo(f"{run_check()} pengingat dikirim")

    @app.cli.command("seed")
    @click.option("--password", default="demo123", help="Password untuk semua akun demo")
    def seed(password):
        """Isi database kosong dengan akun dan data contoh dari seed_data.json."""
        from seed import run
        with app.test_request_context():
            click.echo(run(password))
