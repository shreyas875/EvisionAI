from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel
from ..db import get_db
from ..models.user import User

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterPayload(BaseModel):
    name: str
    username: str
    password: str
    ev_brand: str | None = None
    charger_type: str | None = None
    location: str | None = None


class LoginPayload(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


@router.post("/register")
def register(payload: RegisterPayload, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        name=payload.name,
        username=payload.username,
        password_hash=hash_password(payload.password),
        ev_brand=payload.ev_brand,
        charger_type=payload.charger_type,
        location=payload.location,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registered successfully", "user": {
        "id": user.id, "name": user.name, "username": user.username,
        "ev_brand": user.ev_brand, "charger_type": user.charger_type, "location": user.location
    }}


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Simple session: store user_id in cookie-based session
    request.session["user_id"] = user.id

    return {"message": "Login successful", "user": {
        "id": user.id, "name": user.name, "username": user.username,
        "ev_brand": user.ev_brand, "charger_type": user.charger_type, "location": user.location
    }}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "name": user.name, "username": user.username,
            "ev_brand": user.ev_brand, "charger_type": user.charger_type, "location": user.location}
