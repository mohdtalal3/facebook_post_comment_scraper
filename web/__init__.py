"""Flask application factory."""
import os
import sys

from flask import Flask, jsonify

from scraper.config import bundle_root


def create_app():
    base = bundle_root()
    app = Flask(__name__,
                template_folder=os.path.join(base, "web", "templates"),
                static_folder=os.path.join(base, "web", "static"),
                static_url_path="/static")

    from .routes.views import views_bp
    from .routes.api_scrape import scrape_bp
    from .routes.api_posts import posts_bp
    from .routes.api_settings import settings_bp
    from .routes.api_jobs import jobs_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(scrape_bp, url_prefix="/api")
    app.register_blueprint(posts_bp, url_prefix="/api/posts")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    return app
