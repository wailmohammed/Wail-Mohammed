from backend.app import db # Import db from the app.py
from datetime import datetime

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sector = db.Column(db.String(100), nullable=True) 
    custom_category = db.Column(db.String(100), nullable=True) 
    
    # Relationship to DividendPayment
    dividend_payments = db.relationship('DividendPayment', backref='stock', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Stock {self.symbol} - Sector: {self.sector} - Category: {self.custom_category}>'
