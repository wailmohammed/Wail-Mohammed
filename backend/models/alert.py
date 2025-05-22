from backend.app import db
from datetime import datetime

class PriceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False) # Increased symbol length slightly
    target_price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False, default='above') # "above" or "below"
    status = db.Column(db.String(20), nullable=False, default='active') # "active", "triggered", "cancelled"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # user = db.relationship('User', back_populates='alerts') # Defined in User model

    def __repr__(self):
        return f'<PriceAlert {self.symbol} {self.condition} {self.target_price} ({self.status})>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'target_price': self.target_price,
            'condition': self.condition,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
