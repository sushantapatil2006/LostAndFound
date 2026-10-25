import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import or_, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config
from models import Item, User, db
from storage import LocalStorage, get_storage_provider, validate_image

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def create_app(config_object=Config, storage=None, validate_config=True):
    app = Flask(__name__)
    app.config.from_object(config_object)

    if validate_config and hasattr(config_object, "validate"):
        config_object.validate()

    # Proxy handling for reverse proxy headers (Nginx/Caddy)
    num_proxies = app.config.get("NUM_PROXIES", 1)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=num_proxies,
        x_proto=num_proxies,
        x_host=num_proxies,
        x_prefix=num_proxies,
    )

    CORS(app)
    db.init_app(app)

    # Initialize storage provider
    app.extensions["item_storage"] = storage or get_storage_provider(app.config)

    # Database table initialization (controlled via AUTO_CREATE_TABLES)
    if app.config.get("AUTO_CREATE_TABLES", True):
        with app.app_context():
            db.create_all()

    def issue_token(user):
        expiry = datetime.now(timezone.utc) + timedelta(
            hours=app.config["JWT_EXPIRY_HOURS"]
        )
        return jwt.encode(
            {"sub": str(user.id), "exp": expiry},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    def auth_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Authentication required"), 401
            token_str = header[7:].strip()
            try:
                payload = jwt.decode(
                    token_str, app.config["SECRET_KEY"], algorithms=["HS256"]
                )
                user = db.session.get(User, int(payload["sub"]))
            except jwt.ExpiredSignatureError:
                return jsonify(error="Token has expired"), 401
            except (jwt.InvalidTokenError, ValueError, TypeError):
                return jsonify(error="Invalid or expired token"), 401

            if user is None:
                return jsonify(error="Invalid user or expired token"), 401

            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    # --- Health & Readiness Endpoints ---
    @app.get("/api/health")
    def health():
        """Liveness check endpoint."""
        return jsonify(
            status="ok",
            service="lost-and-found-api",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ), 200

    @app.get("/api/ready")
    def readiness():
        """Readiness check verifying database connectivity."""
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(
                status="ready",
                database="connected",
                timestamp=datetime.now(timezone.utc).isoformat(),
            ), 200
        except Exception as exc:
            app.logger.error(f"Readiness check failed: {exc}")
            return jsonify(
                status="not_ready",
                error="Database connectivity check failed",
            ), 503

    # --- Local Image Serving Endpoint (if LocalStorage used) ---
    @app.get("/api/images/<filename>")
    def serve_image(filename):
        safe_name = secure_filename(filename)
        upload_folder = Path(app.config.get("UPLOAD_FOLDER", "uploads")) / "items"
        return send_from_directory(upload_folder, safe_name)

    # --- Authentication Endpoints ---
    @app.post("/api/register")
    def register():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not all(isinstance(v, str) and v.strip() for v in (name, email, password)):
            return jsonify(error="Name, email, and password are required"), 400

        email = email.strip().lower()
        if not EMAIL_REGEX.match(email):
            return jsonify(error="Invalid email format"), 400

        if len(password) < 8:
            return jsonify(error="Password must be at least 8 characters"), 400

        if User.query.filter_by(email=email).first():
            return jsonify(error="Email is already registered"), 409

        # Security Fix: Admin rights are NEVER automatically granted solely on email address.
        # User must supply a configured bootstrap token, or be promoted via CLI/admin tools.
        is_admin = False
        bootstrap_token = request.headers.get("X-Admin-Bootstrap-Token")
        configured_token = app.config.get("ADMIN_BOOTSTRAP_TOKEN")
        if configured_token and bootstrap_token and bootstrap_token == configured_token:
            is_admin = True
        elif app.config.get("AUTO_ADMIN_REGISTRATION", False) and email in app.config.get("ADMIN_EMAILS", set()):
            # Maintained strictly for backwards compatibility in test environments
            is_admin = True

        user = User(
            name=name.strip(),
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_admin,
        )
        db.session.add(user)
        db.session.commit()

        return jsonify(
            user={"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin},
            token=issue_token(user),
        ), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify(error="Invalid email or password"), 401

        return jsonify(
            user={
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "is_admin": user.is_admin,
            },
            token=issue_token(user),
        )

    # --- Item Endpoints ---
    @app.get("/api/items")
    def items():
        query = Item.query.order_by(Item.created_at.desc())
        item_type = request.args.get("type")
        status = request.args.get("status")
        if item_type in {"lost", "found"}:
            query = query.filter_by(item_type=item_type)
        if status in {"open", "recovered"}:
            query = query.filter_by(status=status)
        return jsonify(items=[item.to_dict() for item in query.all()])

    @app.post("/api/items")
    @auth_required
    def create_item():
        data = request.form
        required = ("title", "description", "item_type", "location")
        if any(not data.get(field, "").strip() for field in required):
            return jsonify(error="Title, description, type, and location are required"), 400

        item_type = data["item_type"].strip().lower()
        if item_type not in {"lost", "found"}:
            return jsonify(error="Type must be lost or found"), 400

        image = request.files.get("image")
        image_name = image_url = None
        if image and image.filename:
            try:
                extension = validate_image(image)
                image_name, image_url = app.extensions["item_storage"].upload(image, extension)
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
            except Exception as exc:
                app.logger.error(f"Image storage upload error: {exc}")
                return jsonify(error="Failed to upload image. Please try again later."), 500

        item = Item(
            title=data["title"].strip(),
            description=data["description"].strip(),
            item_type=item_type,
            location=data["location"].strip(),
            image_object_name=image_name,
            image_url=image_url,
            owner_id=g.current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(item=item.to_dict()), 201

    @app.get("/api/search")
    def search():
        term = request.args.get("q", "").strip()
        if not term:
            return jsonify(error="Search query q is required"), 400
        pattern = f"%{term}%"
        results = (
            Item.query.filter(
                or_(
                    Item.title.ilike(pattern),
                    Item.description.ilike(pattern),
                    Item.location.ilike(pattern),
                )
            )
            .order_by(Item.created_at.desc())
            .all()
        )
        return jsonify(items=[item.to_dict() for item in results])

    @app.patch("/api/items/<int:item_id>/status")
    @auth_required
    def update_status(item_id):
        item = db.session.get(Item, item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        if item.owner_id != g.current_user.id and not g.current_user.is_admin:
            return jsonify(error="Only the owner or an admin can update status"), 403

        status = (request.get_json(silent=True) or {}).get("status")
        if status not in {"open", "recovered"}:
            return jsonify(error="Status must be open or recovered"), 400

        item.status = status
        db.session.commit()
        return jsonify(item=item.to_dict())

    @app.delete("/api/admin/items/<int:item_id>")
    @auth_required
    def admin_delete(item_id):
        if not g.current_user.is_admin:
            return jsonify(error="Administrator access required"), 403
        item = db.session.get(Item, item_id)
        if not item:
            return jsonify(error="Item not found"), 404

        if item.image_object_name:
            try:
                app.extensions["item_storage"].delete(item.image_object_name)
            except Exception as exc:
                app.logger.warning(f"Failed to delete stored image {item.image_object_name}: {exc}")

        db.session.delete(item)
        db.session.commit()
        return jsonify(message="Item deleted")

    # --- Admin Bootstrap Endpoint ---
    @app.post("/api/admin/bootstrap")
    def admin_bootstrap():
        """Promote an existing user to admin if a valid bootstrap token is provided."""
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        token = str(data.get("bootstrap_token", "")).strip()

        configured_token = app.config.get("ADMIN_BOOTSTRAP_TOKEN")
        if not configured_token or not token or token != configured_token:
            return jsonify(error="Unauthorized: Invalid admin bootstrap token"), 403

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify(error="User not found"), 404

        user.is_admin = True
        db.session.commit()
        return jsonify(message=f"User {email} successfully promoted to administrator")

    # --- CLI Commands for Operators ---
    @app.cli.command("init-db")
    def init_db():
        """Initialize database schema tables."""
        db.create_all()
        print("Database schema initialized successfully.")

    @app.cli.command("create-admin")
    def create_admin():
        """Create a new administrator user interactively or promote an existing one."""
        import click

        name = click.prompt("Admin Name")
        email = click.prompt("Admin Email").strip().lower()
        password = click.prompt("Admin Password", hide_input=True)

        user = User.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            print(f"Existing user '{email}' promoted to administrator.")
        else:
            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                is_admin=True,
            )
            db.session.add(user)
            db.session.commit()
            print(f"Administrator '{email}' created successfully.")

    # Serve static frontend files during local development when running standalone Flask
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        @app.get("/")
        def serve_index():
            return send_from_directory(frontend_dir, "index.html")

        @app.get("/<path:filename>")
        def serve_frontend_static(filename):
            if filename.startswith("api/"):
                return jsonify(error="Not found"), 404
            target = frontend_dir / filename
            if target.is_file():
                return send_from_directory(frontend_dir, filename)
            return send_from_directory(frontend_dir, "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true")
    app.run(host=host, port=port, debug=debug)
