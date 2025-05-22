from flask import Blueprint, request, jsonify
from backend.models import PriceAlert, User, db
from backend.routes.auth import token_required
from backend.services.financial_data import get_stock_price, AlphaVantageError # For symbol validation

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

# Create Alert
@alerts_bp.route('', methods=['POST'])
@token_required
def create_alert(current_user):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    errors = {}
    symbol = data.get('symbol')
    target_price_str = data.get('target_price')
    condition = data.get('condition', 'above').lower()

    if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
        errors['symbol'] = 'Symbol is required and must be a string (1-20 chars).'
    
    target_price = None
    if target_price_str is None: # Check for presence
        errors['target_price'] = 'Target price is required.'
    else:
        try:
            target_price = float(target_price_str)
            if target_price <= 0:
                errors['target_price'] = 'Target price must be a positive number.'
        except (ValueError, TypeError):
            errors['target_price'] = 'Target price must be a valid number.'

    if condition not in ['above', 'below']:
        errors['condition'] = 'Condition must be either "above" or "below".'

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    
    # Optional: Validate symbol by trying to fetch its current price
    # Note: get_stock_price returns a dict like {"price": ..., "sector": ...}
    try:
        # Assuming get_stock_price returns a dict like {"price": ..., "sector": ...}
        # or None if the symbol is invalid/not found by the API.
        stock_data_validation = get_stock_price(symbol.upper()) 
        # If using a placeholder API key, this might return mock data or a specific structure indicating mock.
        # If the API key is real, and no price is found (stock_data_validation.get('price') is None),
        # this indicates the symbol might be invalid or not supported by Alpha Vantage.
        if ALPHA_VANTAGE_API_KEY != 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
            if not stock_data_validation or stock_data_validation.get('price') is None:
                 # Check if it's a note about API call frequency
                if stock_data_validation and (stock_data_validation.get("Note") or stock_data_validation.get("Information")):
                     return jsonify({'error': 'API Limit/Error', 'details': f"Could not validate symbol '{symbol.upper()}' due to API limitations or error: {stock_data_validation.get('Note') or stock_data_validation.get('Information')}" }), 400
                return jsonify({'error': 'Validation failed', 'details': {'symbol': f"Symbol '{symbol.upper()}' could not be validated or found via financial API."}}), 400
    except AlphaVantageError as ave:
        # Handle specific AlphaVantage errors if the key is real
        if ALPHA_VANTAGE_API_KEY != 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
            return jsonify({'error': 'API Error', 'details': f"Error validating symbol '{symbol.upper()}': {str(ave)}"}), 503 # Service Unavailable
        print(f"Symbol validation for '{symbol.upper()}' skipped or API error ignored due to placeholder API key.")
    except Exception as e: # Catch any other unexpected error during validation
        if ALPHA_VANTAGE_API_KEY != 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
            print(f"Unexpected error validating symbol '{symbol.upper()}': {e}") # Log for server
            return jsonify({'error': 'Server Error', 'details': f"Unexpected error validating symbol '{symbol.upper()}'."}), 500
        print(f"Symbol validation for '{symbol.upper()}' skipped due to unexpected error with placeholder API key: {e}")

    new_alert = PriceAlert(
        user_id=current_user.id,
        symbol=symbol.upper(),
        target_price=target_price,
        condition=condition,
        status='active' # Default status
    )
    db.session.add(new_alert)
    db.session.commit()
    return jsonify(new_alert.to_dict()), 201

# Get User's Active Alerts
@alerts_bp.route('', methods=['GET'])
@token_required
def get_user_alerts(current_user):
    alerts = PriceAlert.query.filter_by(user_id=current_user.id, status='active').order_by(PriceAlert.created_at.desc()).all()
    return jsonify([alert.to_dict() for alert in alerts]), 200

# Delete Alert
@alerts_bp.route('/<int:alert_id>', methods=['DELETE'])
@token_required
def delete_alert(current_user, alert_id):
    alert = PriceAlert.query.get(alert_id) 
    if not alert:
        return jsonify({'error': 'Not found', 'details': 'Alert not found.'}), 404
    
    if alert.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to delete this alert.'}), 403

    db.session.delete(alert)
    db.session.commit()
    return jsonify({'message': 'Alert deleted successfully.'}), 200
    
# Optional: Update Alert Status 
@alerts_bp.route('/<int:alert_id>/status', methods=['PUT'])
@token_required
def update_alert_status(current_user, alert_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    new_status = data.get('status')

    if not new_status or not isinstance(new_status, str) or new_status.lower() not in ['active', 'triggered', 'cancelled']:
        return jsonify({'error': 'Validation failed', 'details': {'status': 'Invalid status. Must be "active", "triggered", or "cancelled".'}}), 400

    alert = PriceAlert.query.get(alert_id) 
    if not alert:
        return jsonify({'error': 'Not found', 'details': 'Alert not found.'}), 404
    
    if alert.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to update this alert.'}), 403

    alert.status = new_status.lower()
    db.session.commit()
    return jsonify(alert.to_dict()), 200
