from flask import Blueprint, request, jsonify
from backend.models import SubscriptionPlan, CryptoPayment, AdminSetting, db
from backend.routes.auth import token_required
from datetime import datetime

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

@payments_bp.route('/initiate', methods=['POST'])
@token_required
def initiate_crypto_payment(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    plan_id = data.get('plan_id')
    crypto_type = data.get('crypto_type') # e.g., "USDT-TRC20", "BTC"

    errors = {}
    if not plan_id:
        errors['plan_id'] = 'Subscription plan ID is required.'
    else:
        try:
            plan_id = int(plan_id)
        except (ValueError, TypeError):
            errors['plan_id'] = 'Invalid plan ID format.'
            
    if not crypto_type or not isinstance(crypto_type, str):
        errors['crypto_type'] = 'Crypto type is required (e.g., "USDT-TRC20").'
    
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Fetch the selected subscription plan
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        return jsonify({'error': 'Not found', 'details': 'Selected subscription plan not found.'}), 404
    if not plan.is_public: # Ensure user cannot select a hidden admin plan
        return jsonify({'error': 'Forbidden', 'details': 'Selected plan is not available for purchase.'}), 403


    # Fetch the admin's receiving wallet address for the given crypto_type
    # Wallet address setting names should be consistent, e.g., "USDT_TRC20_WALLET_ADDRESS"
    wallet_setting_name = f"{crypto_type.upper().replace('-', '_')}_WALLET_ADDRESS"
    admin_wallet_setting = AdminSetting.query.filter_by(setting_name=wallet_setting_name).first()

    if not admin_wallet_setting or not admin_wallet_setting.setting_value or \
       admin_wallet_setting.setting_value == "YOUR_USDT_TRC20_WALLET_ADDRESS_HERE" or \
       admin_wallet_setting.setting_value == "YOUR_BTC_ADDRESS_HERE": # Check for placeholder
        print(f"Admin wallet for {crypto_type} not configured or is placeholder. Setting: {admin_wallet_setting.setting_value if admin_wallet_setting else 'Not Found'}")
        return jsonify({'error': 'Service Unavailable', 
                        'details': f"Crypto payments for {crypto_type} are not configured yet. Please try another payment method or contact support."}), 503

    receiving_address = admin_wallet_setting.setting_value
    amount_expected_usd = plan.price_monthly # Assuming price is in USD

    # Create a new CryptoPayment record
    new_payment = CryptoPayment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount_expected_usd=amount_expected_usd,
        crypto_type=crypto_type,
        receiving_address=receiving_address,
        status='pending' # Initial status
    )
    db.session.add(new_payment)
    db.session.commit()

    return jsonify({
        'message': 'Payment initiated. Please send the specified amount to the provided address and submit your transaction ID.',
        'payment_id': new_payment.id,
        'plan_name': plan.name,
        'amount_expected_usd': new_payment.amount_expected_usd,
        'crypto_type': new_payment.crypto_type,
        'receiving_address': new_payment.receiving_address,
        'status': new_payment.status,
        'created_at': new_payment.created_at.isoformat()
    }), 201

@payments_bp.route('/<int:payment_id>/submit_txid', methods=['POST'])
@token_required
def submit_transaction_id(current_user, payment_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    transaction_id = data.get('transaction_id')
    if not transaction_id or not isinstance(transaction_id, str) or len(transaction_id.strip()) == 0:
        return jsonify({'error': 'Validation failed', 'details': {'transaction_id': 'Transaction ID is required.'}}), 400
    
    transaction_id = transaction_id.strip()
    if len(transaction_id) > 255: # Check length against model
         return jsonify({'error': 'Validation failed', 'details': {'transaction_id': 'Transaction ID is too long.'}}), 400


    payment = CryptoPayment.query.get(payment_id)
    if not payment:
        return jsonify({'error': 'Not found', 'details': 'Payment record not found.'}), 404

    if payment.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'You are not authorized to update this payment.'}), 403

    if payment.status != 'pending':
        return jsonify({'error': 'Conflict', 
                        'details': f"This payment is not awaiting a transaction ID. Current status: {payment.status}."}), 409

    payment.user_provided_tx_id = transaction_id
    payment.status = 'submitted_tx' # Or 'pending_confirmation'
    payment.updated_at = datetime.utcnow()
    
    db.session.commit()

    return jsonify({
        'message': 'Transaction ID submitted successfully. Your payment will be reviewed by an admin.',
        'payment': payment.to_dict()
    }), 200
