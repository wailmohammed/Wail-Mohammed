from backend.app import db
from datetime import datetime

class DividendPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False) # Total amount received
    pay_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships are typically defined on the "many" side via backref from the "one" side,
    # but explicit relationship() on this side can also be used if preferred.
    # For this structure, backrefs from User and Stock models are cleaner.

    def __repr__(self):
        return f'<DividendPayment ID: {self.id}, StockID: {self.stock_id}, Amount: {self.amount}, Date: {self.pay_date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'pay_date': self.pay_date.isoformat(), # Ensure date is ISO format
            'created_at': self.created_at.isoformat()
        }
