from backend.app import db
from datetime import datetime

class AdminSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_name = db.Column(db.String(100), unique=True, nullable=False) # e.g., "USDT_TRC20_WALLET_ADDRESS"
    setting_value = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AdminSetting {self.setting_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'setting_name': self.setting_name,
            'setting_value': self.setting_value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat()
        }
