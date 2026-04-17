import logging

from sanic import Sanic
from sanic.response import json as json_response
from sanic_cors import CORS

from cd_auth import cd_auth_middleware
from config import config
from blueprints.patients import patients_bp
from blueprints.studies import studies_bp
from blueprints.burn import burn_bp
from blueprints.nodes import nodes_bp
from blueprints.auth import auth_bp

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Sanic("BluePACS_CD")
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.middleware("request")(cd_auth_middleware)


@app.get("/api/access")
async def cd_access_probe(request):
    """Lightweight check for Next.js UI (same auth as other /api routes)."""
    return json_response({"allowed": True})


app.blueprint(auth_bp, url_prefix="/api/auth")
app.blueprint(patients_bp, url_prefix="/api/patients")
app.blueprint(studies_bp, url_prefix="/api/studies")
app.blueprint(burn_bp, url_prefix="/api/burn")
app.blueprint(nodes_bp, url_prefix="/api/nodes")


@app.route("/api/health")
async def health_check(request):
    return json_response({"status": "ok", "service": "BluePACS CD Creator"})


if __name__ == "__main__":
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        auto_reload=config.DEBUG,
    )
