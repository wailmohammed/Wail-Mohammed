from backend.app import db # Import db from the app.py
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Increased length for hash
    stocks = db.relationship('Stock', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Relationship to PriceAlert
    alerts = db.relationship('PriceAlert', backref='user', lazy=True, cascade="all, delete-orphan")
    
    # Relationship to DividendPayment
    dividend_payments = db.relationship('DividendPayment', backref='user_dividend_owner', lazy=True, cascade="all, delete-orphan") # Changed backref name to avoid conflict

    # Relationship to UserSubscription (one-to-one)
    # 'user' backref in UserSubscription will be created automatically by this.
    # uselist=False makes this a one-to-one relationship from the User side.
    subscription = db.relationship('UserSubscription', backref=db.backref('user', uselist=False), lazy='joined', cascade="all, delete-orphan")

    # Relationship to CryptoPayment
    crypto_payments = db.relationship('CryptoPayment', backref='user_payment_owner', lazy=True, cascade="all, delete-orphan")


    def __repr__(self):
        return f'<User {self.username}>'
