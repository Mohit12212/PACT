from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EMAIL_RE, audit, current_user, org_dict, rate_limit
from ..models import ORG_TYPES, Organization, User
from ..security import hash_password, make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=120)
    org_name: str = Field(min_length=2, max_length=120)
    org_type: str = "NGO"
    sector: str = ""
    country: str = ""
    city: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


def me_dict(db, u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "org": org_dict(db, u.org, full=False) if u.org else None}


@router.post("/register", dependencies=[Depends(rate_limit(10))])
def register(b: RegisterIn, db: Session = Depends(get_db)):
    email = b.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if b.org_type not in ORG_TYPES:
        raise HTTPException(422, f"Organisation type must be one of {', '.join(ORG_TYPES)}.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    if db.query(Organization).filter(Organization.name == b.org_name.strip()).first():
        raise HTTPException(409, "An organisation with this name is already registered.")
    org = Organization(name=b.org_name.strip(), type=b.org_type, sector=b.sector, country=b.country, city=b.city, sdgs=[17])
    user = User(email=email, password_hash=hash_password(b.password), full_name=b.full_name.strip(), org=org)
    db.add_all([org, user]); db.flush()
    audit(db, user, "register", org.name); db.commit()
    return {"token": make_token(user.id), "user": me_dict(db, user)}


@router.post("/login", dependencies=[Depends(rate_limit(15))])
def login(b: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == b.email.strip().lower()).first()
    if not u or not u.is_active or not verify_password(b.password, u.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    audit(db, u, "login"); db.commit()
    return {"token": make_token(u.id), "user": me_dict(db, u)}


@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return me_dict(db, u)
