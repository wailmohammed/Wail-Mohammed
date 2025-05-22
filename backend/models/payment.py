from backend.app import db
from datetime import datetime

class CryptoPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=True) 
    
    amount_expected_usd = db.Column(db.Float, nullable=False)
    crypto_type = db.Column(db.String(50), nullable=False) # e.g., "USDT-TRC20", "BTC"
    receiving_address = db.Column(db.String(255), nullable=False) # The address user was shown
    user_provided_tx_id = db.Column(db.String(255), nullable=True) # Transaction ID provided by user
    
    status = db.Column(db.String(50), nullable=False, default='pending') 
    # Possible statuses: 
    # 'pending' (awaiting user TX_ID submission), 
    # 'submitted_tx' (user submitted TX_ID, awaiting confirmation), 
    # 'confirmed' (payment verified), 
    # 'failed' (e.g., TX_ID invalid, amount mismatch after check), 
    # 'expired' (payment window closed before submission)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    # Relationships will be set up via backref from User and SubscriptionPlan models
    # user = db.relationship('User', backref=db.backref('crypto_payments', lazy=True))
    # plan = db.relationship('SubscriptionPlan', backref=db.backref('crypto_payments', lazy=True))


    def __repr__(self):
        return f'<CryptoPayment {self.id} UserID:{self.user_id} {self.crypto_type} {self.amount_expected_usd} USD Status:{self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'plan_name': self.plan.name if self.plan else None, # Assuming backref 'plan' from SubscriptionPlan is set up
            'amount_expected_usd': self.amount_expected_usd,
            'crypto_type': self.crypto_type,
            'receiving_address': self.receiving_address,
            'user_provided_tx_id': self.user_provided_tx_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None
        }
