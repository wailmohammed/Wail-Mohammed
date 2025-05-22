from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portfolio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Import models here to ensure they are registered with SQLAlchemy
from backend.models import User, Stock # Adjusted import path

# Import blueprints
from backend.routes.auth import auth_bp
from backend.routes.portfolio import portfolio_bp 
from backend.routes.alerts import alerts_bp 
from backend.routes.admin import admin_bp 
from backend.routes.subscriptions import subscriptions_bp 
from backend.routes.user import user_bp 
from backend.routes.payments import payments_bp # Import payments blueprint
from backend.models.subscription import SubscriptionPlan # Import for seeding

# Register Blueprints
app.register_blueprint(auth_bp) 
app.register_blueprint(portfolio_bp) 
app.register_blueprint(alerts_bp) 
app.register_blueprint(admin_bp) 
app.register_blueprint(subscriptions_bp) 
app.register_blueprint(user_bp) 
app.register_blueprint(payments_bp) # Register payments_bp

def seed_subscription_plans():
    """Seeds the database with default subscription plans if they don't exist."""
    print("Attempting to seed subscription plans...")
    # Plan definitions
    plans_data = [
        {
            "name": "Free", "price_monthly": 0.0, "max_stocks": 10,
            "allow_custom_categories": False, "allow_dividend_tracking": False,
            "allow_benchmarking": False, "allow_csv_import": False, "allow_api_access": False, 
            "allow_generic_import": False, "is_public": True
        },
        {
            "name": "Pro", "price_monthly": 10.0, "max_stocks": 100,
            "allow_custom_categories": True, "allow_dividend_tracking": True,
            "allow_benchmarking": True, "allow_csv_import": True, "allow_api_access": False, 
            "allow_generic_import": True, "is_public": True # Enable for Pro
        },
        {
            "name": "Premium", "price_monthly": 25.0, "max_stocks": None, 
            "allow_custom_categories": True, "allow_dividend_tracking": True,
            "allow_benchmarking": True, "allow_csv_import": True, "allow_api_access": True, 
            "allow_generic_import": True, "is_public": True # Enable for Premium
        }
    ]

    for plan_data in plans_data:
        plan = SubscriptionPlan.query.filter_by(name=plan_data["name"]).first()
        if not plan:
            new_plan = SubscriptionPlan(**plan_data)
            db.session.add(new_plan)
            print(f"Added plan: {new_plan.name}")
        else:
            # Update existing plans if they differ (e.g., when adding a new flag)
            updated = False
            for key, value in plan_data.items():
                if getattr(plan, key) != value:
                    setattr(plan, key, value)
                    updated = True
            if updated:
                print(f"Plan '{plan.name}' updated.")
            else:
                print(f"Plan '{plan.name}' already exists and is up to date.")
            
    db.session.commit()
    print("Subscription plan seeding complete.")

# Create a CLI command to seed data
import click
@app.cli.command("seed-plans")
def seed_plans_command():
    """Seeds the database with initial subscription plans."""
    seed_subscription_plans()
    click.echo("Seeded subscription plans.")

# Ensure all models are imported before create_all is called.
# This is typically done by importing the models package or specific models.
from backend import models # Ensures all models in models/* and models/__init__.py are processed by SQLAlchemy

with app.app_context():
    db.create_all() # Creates tables if they don't exist
    # You might want to call seed_subscription_plans() here for automatic seeding on first run,
    # but using a CLI command is often preferred for more control.
    # For this environment, let's try calling it directly to ensure seeding if CLI is not used.
    # However, check if it's already been seeded to avoid issues on every app start.
    if SubscriptionPlan.query.count() == 0: 
        print("No subscription plans found, attempting to seed...")
        seed_subscription_plans()
    else:
        print(f"{SubscriptionPlan.query.count()} subscription plans already exist. Skipping seed.")

    # Seed Admin Settings (e.g., Wallet Addresses)
    from backend.models.admin_setting import AdminSetting # Import AdminSetting
    
    def seed_admin_settings():
        print("Attempting to seed admin settings...")
        default_settings = [
            {
                "setting_name": "USDT_TRC20_WALLET_ADDRESS",
                "setting_value": "YOUR_USDT_TRC20_WALLET_ADDRESS_HERE", # Admin should update this
                "description": "Admin's USDT (TRC-20) wallet for receiving payments."
            },
            # Add other crypto wallet addresses or settings here as needed
            # e.g., {"setting_name": "BTC_WALLET_ADDRESS", "setting_value": "YOUR_BTC_ADDRESS_HERE", ...}
        ]
        for setting_data in default_settings:
            setting = AdminSetting.query.filter_by(setting_name=setting_data["setting_name"]).first()
            if not setting:
                new_setting = AdminSetting(**setting_data)
                db.session.add(new_setting)
                print(f"Added admin setting: {new_setting.setting_name}")
            else:
                # Optionally update description if it changed, but leave value as is unless explicitly managed.
                # For wallet addresses, admin should set the value.
                if setting.setting_value == "YOUR_USDT_TRC20_WALLET_ADDRESS_HERE" or \
                   setting.setting_value == "YOUR_BTC_ADDRESS_HERE": # Check if it's still the placeholder
                   print(f"Admin setting '{setting.setting_name}' exists but is a placeholder. Please update it via Admin Panel.")
                else:
                   print(f"Admin setting '{setting.setting_name}' already exists.")
        db.session.commit()
        print("Admin settings seeding/check complete.")

    if AdminSetting.query.count() == 0: # Only seed if no admin settings exist
        print("No admin settings found, attempting to seed...")
        seed_admin_settings()
    else:
        # Check for specific placeholder values if needed, or just confirm existing settings.
        print(f"{AdminSetting.query.count()} admin settings already exist. Ensure they are correctly configured.")
        # Example: Check if the USDT address is still the placeholder
        usdt_setting = AdminSetting.query.filter_by(setting_name="USDT_TRC20_WALLET_ADDRESS").first()
        if usdt_setting and usdt_setting.setting_value == "YOUR_USDT_TRC20_WALLET_ADDRESS_HERE":
            print("WARNING: USDT_TRC20_WALLET_ADDRESS is still set to the placeholder value.")


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'" # Example, more specific needed
    # CSP is better handled by meta tag in HTML for static sites, or more complex setup for dynamic content.
    # The meta tag in stock_portfolio_tracker.html is the primary CSP source for the frontend.
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # For HSTS, uncomment and configure if HTTPS is enforced:
    # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.route('/')
def index():
    return "Backend is running"

if __name__ == '__main__':
    app.run(debug=True)

# Ensure models are imported before db.create_all() or migrations are run
# This is often done by importing them in __init__.py of the models package
# and then ensuring that package is imported, or by direct imports like above.
