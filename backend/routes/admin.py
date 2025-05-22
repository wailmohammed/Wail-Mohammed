from flask import Blueprint, jsonify
from backend.models import User, Stock, PriceAlert, db # Added PriceAlert for more stats
from backend.routes.auth import admin_required # Import the new decorator
from backend.services.financial_data import get_stock_price, AlphaVantageError, ALPHA_VANTAGE_API_KEY
import requests # For broader request exception catching

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/stats/users', methods=['GET'])
@admin_required
def user_statistics(current_user): # current_user is passed by @admin_required
    total_users = User.query.count()
    total_stocks_tracked = Stock.query.count()
    total_price_alerts_active = PriceAlert.query.filter_by(status='active').count()
    
    # More detailed user stats (example)
    users_with_portfolios = User.query.join(User.stocks).distinct().count()
    users_with_alerts = User.query.join(User.alerts).distinct().count()


    return jsonify({
        "total_users": total_users,
        "users_with_portfolios": users_with_portfolios,
        "users_with_active_alerts": users_with_alerts,
        "total_stocks_tracked_overall": total_stocks_tracked,
        "total_active_price_alerts_overall": total_price_alerts_active
    }), 200

@admin_bp.route('/stats/system', methods=['GET'])
@admin_required
def system_status(current_user):
    db_status = "Online" # If this endpoint works, DB is implicitly online for basic queries

    alpha_vantage_status = "Unknown"
    # Check Alpha Vantage status only if API key is not the placeholder
    if ALPHA_VANTAGE_API_KEY != 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        try:
            # Make a non-cached call if possible, or just use existing.
            # get_stock_price now returns a dict, so check its result.
            test_data = get_stock_price('IBM') # Using a common symbol like IBM
            if test_data and test_data.get('price') is not None:
                alpha_vantage_status = "Online"
            elif test_data and test_data.get('price') is None and test_data.get('sector') is not None : 
                # This case means AV returned overview but no price for IBM (unlikely for IBM but good check)
                alpha_vantage_status = "Partially Online (Overview working, Global Quote issue for IBM)"
            else:
                # This might happen if the API returns an empty response for Global Quote
                # or if the mock data for 'UNKNOWN' in get_stock_price is returned (which it shouldn't if key is not placeholder)
                alpha_vantage_status = "Error (No price for IBM)"
        except AlphaVantageError as ave:
            alpha_vantage_status = f"Error ({str(ave)})"
        except requests.exceptions.RequestException as re: # Catch broader network issues
            alpha_vantage_status = f"Offline (Network Error: {str(re)})"
        except Exception as e: # Catch any other unexpected error
            alpha_vantage_status = f"Error (Unexpected: {str(e)})"
    else:
        alpha_vantage_status = "Not Monitored (API Key is Placeholder)"


    return jsonify({
        "database_status": db_status,
        "alpha_vantage_api_status": alpha_vantage_status
    }), 200

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        if page <= 0:
            return jsonify({'error': 'Validation failed', 'details': {'page': 'Page number must be positive.'}}), 400
        if per_page <= 0 or per_page > 100: # Cap per_page to a reasonable limit
            return jsonify({'error': 'Validation failed', 'details': {'per_page': 'Per-page limit must be between 1 and 100.'}}), 400
            
    except ValueError: # Catches if type=int fails for non-integer query params
        return jsonify({'error': 'Bad Request', 'details': 'Invalid page or per_page parameters. Must be integers.'}), 400

    
    users_pagination = User.query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
    users_data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'stocks_count': len(user.stocks),
        'alerts_count': len(user.alerts)
    } for user in users_pagination.items]
    
    return jsonify({
        'users': users_data,
        'total_users': users_pagination.total,
        'current_page': users_pagination.page,
        'total_pages': users_pagination.pages
    }), 200

from backend.models.admin_setting import AdminSetting # Import AdminSetting

# Get all Admin Settings (includes wallet addresses)
@admin_bp.route('/settings', methods=['GET'])
@admin_required
def get_all_admin_settings(current_user):
    settings = AdminSetting.query.all()
    return jsonify([setting.to_dict() for setting in settings]), 200

# Update a specific Admin Setting (e.g., a wallet address)
@admin_bp.route('/settings/<string:setting_name>', methods=['PUT'])
@admin_required
def update_admin_setting(current_user, setting_name):
    data = request.get_json()
    if not data or 'setting_value' not in data:
        return jsonify({'error': 'Bad Request', 'details': 'Missing setting_value in request body.'}), 400

    new_value = data['setting_value']
    if not isinstance(new_value, str) or len(new_value) > 255 :
         return jsonify({'error': 'Validation failed', 'details': {'setting_value': 'Value must be a string up to 255 characters.'}}), 400


    setting_name_upper = setting_name.upper() # Ensure consistency if needed
    setting = AdminSetting.query.filter_by(setting_name=setting_name_upper).first()

    if not setting:
        # Option to create if not exists, or return 404. For wallets, admin should generally create them if needed.
        # For this example, let's assume settings are pre-defined or created via a seed/another interface.
        # If we want to allow creation here:
        # setting = AdminSetting(setting_name=setting_name_upper, setting_value=new_value, description=f"Managed setting for {setting_name_upper}")
        # db.session.add(setting)
        # print(f"Admin setting '{setting_name_upper}' created by admin {current_user.id}")
        return jsonify({'error': 'Not found', 'details': f"Setting '{setting_name_upper}' not found."}), 404


    setting.setting_value = new_value
    setting.updated_at = datetime.utcnow() 
    db.session.commit()
    
    return jsonify({'message': f"Setting '{setting.setting_name}' updated successfully.", 'setting': setting.to_dict()}), 200

from backend.models.payment import CryptoPayment # Import CryptoPayment
from backend.models.subscription import UserSubscription, SubscriptionPlan # For updating user's sub
from dateutil.relativedelta import relativedelta # For calculating end_date

# Admin: List Pending Crypto Payments
@admin_bp.route('/payments/pending', methods=['GET'])
@admin_required
def admin_list_pending_payments(current_user):
    # Fetch payments that admin needs to review (e.g., status 'submitted_tx')
    pending_payments = CryptoPayment.query.filter(CryptoPayment.status.in_(['submitted_tx', 'pending_confirmation'])).order_by(CryptoPayment.updated_at.asc()).all()
    
    payments_data = []
    for payment in pending_payments:
        payment_dict = payment.to_dict()
        # Add user and plan info for admin context
        payment_dict['user_email'] = payment.user_payment_owner.email # Assuming 'user_payment_owner' is the backref from CryptoPayment to User
        payment_dict['plan_name'] = payment.plan.name if payment.plan else "N/A" # Assuming 'plan' is backref from CryptoPayment to SubscriptionPlan
        payments_data.append(payment_dict)
        
    return jsonify(payments_data), 200

# Admin: Confirm a Crypto Payment
@admin_bp.route('/payments/<int:payment_id>/confirm', methods=['POST'])
@admin_required
def admin_confirm_payment(current_user, payment_id):
    payment = CryptoPayment.query.get(payment_id)
    if not payment:
        return jsonify({'error': 'Not found', 'details': 'Crypto payment record not found.'}), 404

    if payment.status not in ['submitted_tx', 'pending_confirmation']: # Or just 'submitted_tx'
        return jsonify({'error': 'Conflict', 'details': f"Payment is not awaiting confirmation. Current status: {payment.status}"}), 409

    payment.status = 'confirmed'
    payment.confirmed_at = datetime.utcnow()
    
    # Update user's subscription
    user_to_update = User.query.get(payment.user_id)
    if not user_to_update:
        # This should ideally not happen if DB is consistent
        db.session.rollback() # Rollback payment status change
        return jsonify({'error': 'Server Error', 'details': 'User associated with payment not found.'}), 500

    # Calculate subscription duration (e.g., 30 days for monthly plans)
    # This is a simplification. More complex logic might be needed for different plan durations.
    # Assuming all plans are monthly for now for simplicity.
    subscription_duration_days = 30 
    
    if user_to_update.subscription:
        user_to_update.subscription.plan_id = payment.plan_id
        user_to_update.subscription.status = 'active'
        # If already active, extend; if expired/trialing, start new period
        current_start_date = user_to_update.subscription.start_date
        current_end_date = user_to_update.subscription.end_date
        now = datetime.utcnow()

        # If current subscription is active and has a future end_date, extend it.
        # Otherwise, start a new period from today.
        if user_to_update.subscription.status == 'active' and current_end_date and current_end_date > now:
            user_to_update.subscription.start_date = current_end_date # Start new period after old one ends
            user_to_update.subscription.end_date = current_end_date + relativedelta(days=subscription_duration_days)
        else: # New subscription period or reactivating
            user_to_update.subscription.start_date = now
            user_to_update.subscription.end_date = now + relativedelta(days=subscription_duration_days)
        
        user_to_update.subscription.trial_ends_at = None # Clear any trial period
        db.session.add(user_to_update.subscription)
    else: # Should not happen if default 'Free' or 'Pro Trial' plan is assigned on registration
        db.session.rollback()
        return jsonify({'error': 'Server Error', 'details': 'User has no existing subscription record to update.'}), 500
        
    db.session.commit()
    return jsonify({'message': 'Payment confirmed and subscription updated.', 'payment': payment.to_dict()}), 200

# Admin: Mark a Crypto Payment as Failed
@admin_bp.route('/payments/<int:payment_id>/fail', methods=['POST'])
@admin_required
def admin_fail_payment(current_user, payment_id):
    payment = CryptoPayment.query.get(payment_id)
    if not payment:
        return jsonify({'error': 'Not found', 'details': 'Crypto payment record not found.'}), 404

    # Allow failing payments that were submitted or even pending if admin deems necessary
    if payment.status not in ['submitted_tx', 'pending_confirmation', 'pending']:
         return jsonify({'error': 'Conflict', 'details': f"Payment status is '{payment.status}', cannot mark as failed unless it's pending or submitted."}), 409

    payment.status = 'failed'
    payment.updated_at = datetime.utcnow()
    # Optionally add a reason for failure from request.json() if needed
    # e.g. payment.failure_reason = data.get('reason')
    db.session.commit()
    
    return jsonify({'message': 'Payment marked as failed.', 'payment': payment.to_dict()}), 200
