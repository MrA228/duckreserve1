# Importing stuff
import os
import qrcode
import base64
import stripe
from flask import Flask, render_template, redirect, request, session
from flask_session import Session
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Table, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from helpers import login_required, admin_required
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv





load_dotenv()
# Configuring Application
app = Flask(__name__)

# Configure System to Use Filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.secret_key = os.environ.get("SECRET_KEY")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLIC = os.environ.get("STRIPE_PUBLIC_KEY")

DATABASE_URL = os.environ.get("DATABASE_URL")

# Render gives postgres:// but SQLAlchemy + psycopg needs postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, echo=True)

Base = declarative_base()



# Table of users
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)

# Table of Rooms
class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    tables = relationship("Table", back_populates="room")

# Table of TABLES (pun intended) in a Room
class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    seats = Column(Integer, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"))

    room = relationship("Room", back_populates="tables")

    reservations = relationship(
        "Reservation", 
        back_populates="table",
    )

# Table of Reservations. WHO booked each table?
class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    table_id = Column(Integer, ForeignKey("tables.id"))
    active = Column(Boolean, nullable=False, default=True)
    timestamp = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    time_slot = Column(String, nullable=False)

    user = relationship("User", backref="reservations")
    
    table = relationship("Table", 
        back_populates="reservations"
    )


TIME_SLOTS = [
    "10:00-11:00",
    "11:00-12:00",
    "12:00-13:00",
    "13:00-14:00",
    "14:00-15:00",
    "15:00-16:00",
    "16:00-17:00",
    "17:00-18:00",
    "18:00-19:00",
    "19:00-20:00",
]

# Build the tables
Base.metadata.create_all(engine)

# Create the session look-after-er
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def seed_rooms_and_tables():
    room_names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]

    admin_pass = os.environ.get("ADMIN_PASSWORD")
    if not admin_pass:
        raise Exception("ADMIN_PASSWORD was not set")

    # Creating admin
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        admin = User(
            username = "admin",
            password_hash = generate_password_hash(admin_pass),
            is_admin = True,
        )
        db.add(admin)
        db.commit()
        print("Admin created")
    else:
        print("Admin already exists.")
    

    # If rooms already exist, skip seeding
    if db.query(Room).count() > 0:
        print("Rooms already exist - skipping seeding.")
        return
    
    print("Alr, seeding rooms and tables...")

    # Creating each room

    for name in room_names:
        room = Room(name=name)
        db.add(room)
        db.commit()
        # room id should be available now

        # creating 16 tables inside the room
        for i in range(1, 17):
            table = Table(
                name=f"{name}-{i}",
                seats=4,
                room_id=room.id,
            )
            db.add(table)
        db.commit()
    print("Alr, seeding complete V")
    
with app.app_context():
    try:
        # Only seed if no rooms exist
        if db.query(Room).count() == 0:
            print("Database empty → Seeding rooms & admin...")
            seed_rooms_and_tables()
        else:
            print("Database already seeded.")
    except Exception as e:
        print("Seeding check failed:", e)

# Main page with welcome and free tables
@app.route("/")
def index():
    rooms = db.query(Room).all()
    return render_template("index.html", rooms=rooms)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return "Missing Username", 400
        if not password:
            return "Missing Password", 400
        user = db.query(User).filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            return render_template("login.html", error="Invalid Username and/or Password")
        
        session["user_id"] = user.id
        session["is_admin"] = user.is_admin
        
        print(session)
        return redirect("/")
    return render_template("login.html")

# Logging out (bye bye!)
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
# Registering the user
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return "Missing Username", 400
        if not password:
            return "Missing Password", 400
        if not confirmation:
            return "Missing Confirmation (password)", 400
        
        if password != confirmation:
            return render_template("register.html", error="Passwords do not match")
        
        usercheck = db.query(User).filter_by(username=username).first()
        if usercheck:
            return render_template("register.html", error="This User Already exists.")

        passhash = generate_password_hash(password)

        registering = User(username=username, password_hash=passhash)
        db.add(registering)
        db.commit()

        return redirect("/login")
    return render_template("register.html")

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_panel():
    rooms = db.query(Room).all()
    reservations = db.query(Reservation).filter_by(active=True).all()
    return render_template("admin.html", rooms=rooms, reservations=reservations)

@app.route("/admin/free/<int:table_id>")
@admin_required
def admin_free(table_id):  
    
    slot = request.args.get("slot")
    if not slot:
        return "Slot is required", 400
    
    res = db.query(Reservation).filter_by(table_id=table_id, time_slot=slot, active=True).first()
    if not res:
        return "There is not reservation for this slot", 404
    
    res.active = False

    db.commit()

    return redirect(f"/table/{table_id}")

@app.route("/room/<int:room_id>")
def room(room_id):
    room = db.query(Room).filter_by(id=room_id).first()

    if not room:
        return "Room not found", 404
    
    tables = db.query(Table).filter_by(room_id=room_id).all()

    return render_template("room.html", room=room, tables=tables)

@app.route("/reserve/<int:table_id>", methods=["GET", "POST"])
@login_required
def reserve(table_id):

    slot = request.args.get("slot")
    if not slot:
        return "No time slot selected", 400

    # Finding the table
    table = db.query(Table).filter_by(id=table_id).first()
    if not table:
        return "Table not found", 404
    
    # Checking if the slot is already reserved
    
    exists = db.query(Reservation).filter_by(table_id=table_id, time_slot=slot, active=True).first()
    if exists:
        return "Time slot already reserved"
    
    # You cannot reserve some other table at this time
    existing = db.query(Reservation).filter_by(user_id=session["user_id"], time_slot = slot, active=True).first()

    if existing:
        return "You already have reserved a table at this time", 400

    
    # Creating a record of reservation
    new_reservation = Reservation(
        user_id = session["user_id"],
        table_id = table.id,
        time_slot = slot,
        active = True,
    )
    db.add(new_reservation)

    # Save Changes
    db.commit()
    return redirect(f"/table/{table_id}")


@app.route("/table/<int:table_id>")
def table_details(table_id):
    table = db.query(Table).filter_by(id=table_id).first()

    if not table:
        return "Table not found", 404
    
    # all the active reservations on the particular table

    
    reservations = db.query(Reservation).filter_by(table_id=table_id, active=True).all()
    taken_slots = { r.time_slot for r in reservations }
    return render_template("table_details.html", table=table, reservations=reservations, taken=taken_slots, times=TIME_SLOTS)

@app.route("/cancel/<int:table_id>")
@login_required
def cancel(table_id):
    
    slot = request.args.get("slot")
    if not slot:
        return "Slot is required", 400


    # Finding the table
    table = db.query(Table).filter_by(id=table_id).first()
    if not table:
        return "Table not found", 404
    
    
    reservation = db.query(Reservation).filter_by(table_id=table_id, user_id=session["user_id"], time_slot=slot, active=True).first()
    if not reservation:
        return "You have no active reservations at this time", 400
    
    # Making sure if the user actually is THE ONE who reserved the table

    if reservation.user_id != session["user_id"]:
        return "You cannot cancel another user's reservation", 403
    

    # Marking the reservation as inactive
    reservation.active = False

    db.commit()

    return redirect(f"/table/{table_id}")

@app.route("/myreservations")
@login_required
def myreservations():
    user_id = session["user_id"]

    # Trying out if i can write the dots on the separate line
    active_reservations = (
        db.query(Reservation)
        .filter_by(user_id=user_id, active=True)
        .all()
    )

    past_reservations = db.query(Reservation).filter_by(user_id=user_id, active=False).all()

    for r in past_reservations:
        r._table_obj = db.query(Table).filter_by(id=r.table_id).first()
    
    for r in active_reservations:
        r._table_obj = db.query(Table).filter_by(id=r.table_id).first()

    return render_template("myreservations.html", active=active_reservations, history=past_reservations)

@app.route("/account")
@login_required
def myaccount():
    
    user = db.query(User).filter_by(id=session["user_id"]).first()

    total_reservations = db.query(Reservation).filter_by(user_id=user.id).count()

    # Generating a cool QR code for the user id
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(f"USER_ID:{user.id}")
    qr.make(fit=True)


    img = qr.make_image(fill="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_image = base64.b64encode(buffer.getvalue()).decode()

    return render_template("myaccount.html", user=user, total_reservations=total_reservations, qr_image=qr_image)

@app.route("/changepassword", methods=["POST"])
@login_required
def change_password():

    old = request.form.get("old")
    new = request.form.get("new")
    confirm = request.form.get("confirm")

    user = db.query(User).filter_by(id=session["user_id"]).first()

    if not check_password_hash(user.password_hash, old):
        return "Incorrect old password", 400
    
    if new != confirm:
        return "Passwords do not match", 400

    user.password_hash = generate_password_hash(new)
    db.commit()

    return redirect("/account")

@app.route("/deleteaccount", methods=["POST"])
@login_required
def delete_account():
    user = db.query(User).filter_by(id=session["user_id"]).first()

    # deleting user's reservations before deleting them
    db.query(Reservation).filter_by(user_id=user.id).delete()

    db.delete(user)
    db.commit()

    session.clear()

    return redirect("/")





@app.route("/pay/<int:table_id>")
@login_required
def pay(table_id):


    slot = request.args.get("slot")
    if not slot:
        return "No time slot selected", 400
    
    DOMAIN = os.environ.get("DOMAIN")
    
    checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"Reservation for table {table_id} ({slot})"
                },
                "unit_amount": 500 # 500 cents
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{DOMAIN}/afterpayment?session_id={{CHECKOUT_SESSION_ID}}&table={table_id}&slot={slot}",
        cancel_url=f"{DOMAIN}/table/{table_id}"
    )

    return redirect(checkout.url)

@app.route("/afterpayment")
@login_required
def after_payment():

    session_id = request.args.get("session_id")
    table_id = request.args.get("table")
    slot = request.args.get("slot")

    stripe_session = stripe.checkout.Session.retrieve(session_id)

    if stripe_session.payment_status != "paid":
        return "Payment failed", 400
    
    # Reserving safely

    return redirect(f"/reserve/{table_id}?slot={slot}")

