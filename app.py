from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models import Item, User, db
from storage import OCIStorage, validate_image


def create_app(config_object=Config, storage=None):
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app)
    db.init_app(app)
    app.extensions["item_storage"] = storage or OCIStorage(app.config)

    with app.app_context():
        db.create_all()

    def issue_token(user):
        expiry = datetime.now(timezone.utc) + timedelta(
            hours=app.config["JWT_EXPIRY_HOURS"]
        )
        return jwt.encode({"sub": str(user.id), "exp": expiry}, app.config["SECRET_KEY"], algorithm="HS256")

    def auth_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Authentication required"), 401
            try:
                payload = jwt.decode(
                    header[7:], app.config["SECRET_KEY"], algorithms=["HS256"]
                )
                user = db.session.get(User, int(payload["sub"]))
            except (jwt.InvalidTokenError, ValueError, TypeError):
                user = None
            if user is None:
                return jsonify(error="Invalid or expired token"), 401
            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    @app.post("/api/register")
    def register():
        data = request.get_json(silent=True) or {}
        name, email, password = data.get("name"), data.get("email"), data.get("password")
        if not all(isinstance(value, str) and value.strip() for value in (name, email, password)):
            return jsonify(error="Name, email, and password are required"), 400
        email = email.strip().lower()
        if len(password) < 8:
            return jsonify(error="Password must be at least 8 characters"), 400
        if User.query.filter_by(email=email).first():
            return jsonify(error="Email is already registered"), 409
        user = User(
            name=name.strip(),
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=email in app.config["ADMIN_EMAILS"],
        )
        db.session.add(user)
        db.session.commit()
        return jsonify(user={"id": user.id, "name": user.name, "email": user.email}, token=issue_token(user)), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
        if not user or not check_password_hash(user.password_hash, data.get("password", "")):
            return jsonify(error="Invalid email or password"), 401
        return jsonify(user={"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}, token=issue_token(user))

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
        if data["item_type"] not in {"lost", "found"}:
            return jsonify(error="Type must be lost or found"), 400
        image = request.files.get("image")
        image_name = image_url = None
        if image:
            try:
                extension = validate_image(image)
                image_name, image_url = app.extensions["item_storage"].upload(image, extension)
            except ValueError as exc:
                return jsonify(error=str(exc)), 400
        item = Item(
            title=data["title"].strip(),
            description=data["description"].strip(),
            item_type=data["item_type"],
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
        results = Item.query.filter(
            or_(Item.title.ilike(pattern), Item.description.ilike(pattern), Item.location.ilike(pattern))
        ).order_by(Item.created_at.desc()).all()
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
            app.extensions["item_storage"].delete(item.image_object_name)
        db.session.delete(item)
        db.session.commit()
        return jsonify(message="Item deleted")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
