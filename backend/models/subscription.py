from backend.app import db
from datetime import datetime

class SubscriptionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    price_monthly = db.Column(db.Float, nullable=False)
    max_stocks = db.Column(db.Integer, nullable=True)  # None for unlimited
    allow_custom_categories = db.Column(db.Boolean, default=False, nullable=False)
    allow_dividend_tracking = db.Column(db.Boolean, default=False, nullable=False)
    allow_benchmarking = db.Column(db.Boolean, default=False, nullable=False)
    allow_csv_import = db.Column(db.Boolean, default=False, nullable=False)
    allow_api_access = db.Column(db.Boolean, default=False, nullable=False) 
    allow_generic_import = db.Column(db.Boolean, default=False, nullable=False) # New feature flag
    is_public = db.Column(db.Boolean, default=True, nullable=False) 

    # Relationship: A plan can have many user subscriptions
    user_subscriptions = db.relationship('UserSubscription', backref='plan', lazy=True)
    # Relationship to CryptoPayment (one plan can be paid for by many crypto payments)
    crypto_payments = db.relationship('CryptoPayment', backref='plan', lazy=True)


    def __repr__(self):
        return f'<SubscriptionPlan {self.name} - ${self.price_monthly}/month>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price_monthly': self.price_monthly,
            'max_stocks': self.max_stocks,
            'allow_custom_categories': self.allow_custom_categories,
            'allow_dividend_tracking': self.allow_dividend_tracking,
            'allow_benchmarking': self.allow_benchmarking,
            'allow_csv_import': self.allow_csv_import,
            'allow_api_access': self.allow_api_access,
            'allow_generic_import': self.allow_generic_import, # Add to to_dict
            'is_public': self.is_public
        }

class UserSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True) # One active subscription per user
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True) # For fixed-term subscriptions
    trial_ends_at = db.Column(db.DateTime, nullable=True) # For trial periods
    status = db.Column(db.String(50), nullable=False, default='active') # e.g., 'active', 'expired', 'trialing', 'cancelled', 'past_due'

    # Relationship to User is defined via backref in User model
    # Relationship to SubscriptionPlan is defined via backref 'plan' from SubscriptionPlan model

    def __repr__(self):
        return f'<UserSubscription UserID: {self.user_id}, PlanID: {self.plan_id}, Status: {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'plan_name': self.plan.name if self.plan else None, # Include plan name for convenience
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'status': self.status
        }
