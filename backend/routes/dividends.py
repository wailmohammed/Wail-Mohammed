from flask import Blueprint, request, jsonify
from backend.models import DividendPayment, Stock, db
from backend.routes.auth import token_required, subscription_required # Import subscription_required
from datetime import datetime

dividends_bp = Blueprint('dividends', __name__, url_prefix='/api') 

# Add Dividend Payment for a Specific Stock
@dividends_bp.route('/stocks/<int:stock_id>/dividends', methods=['POST'])
@subscription_required('allow_dividend_tracking')
def add_dividend_for_stock(current_user, stock_id):
    # Verify stock exists and belongs to the current user
    stock = Stock.query.filter_by(id=stock_id, user_id=current_user.id).first()
    if not stock:
        return jsonify({'error': 'Not found', 'details': 'Stock not found or you do not own this stock.'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    errors = {}
    amount_str = data.get('amount')
    pay_date_str = data.get('pay_date')

    amount = None
    if amount_str is None:
        errors['amount'] = 'Dividend amount is required.'
    else:
        try:
            amount = float(amount_str)
            if amount <= 0:
                errors['amount'] = 'Amount must be a positive number.'
        except (ValueError, TypeError):
            errors['amount'] = 'Amount must be a valid number.'

    pay_date = None
    if not pay_date_str:
        errors['pay_date'] = 'Payment date is required.'
    else:
        try:
            if not isinstance(pay_date_str, str):
                 raise ValueError("Date must be a string.")
            pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d').date() # Expecting YYYY-MM-DD date format
        except ValueError:
            errors['pay_date'] = 'Invalid date format. Please use YYYY-MM-DD.'
    
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    new_dividend = DividendPayment(
        stock_id=stock_id,
        user_id=current_user.id,
        amount=amount,
        pay_date=pay_date
    )
    db.session.add(new_dividend)
    db.session.commit()
    return jsonify(new_dividend.to_dict()), 201


# List Dividend Payments for a Specific Stock
@dividends_bp.route('/stocks/<int:stock_id>/dividends', methods=['GET'])
@subscription_required('allow_dividend_tracking')
def get_dividends_for_stock(current_user, stock_id):
    # Verify stock exists and belongs to the current user
    stock = Stock.query.filter_by(id=stock_id, user_id=current_user.id).first()
    if not stock:
        return jsonify({'error': 'Not found', 'details': 'Stock not found or you do not own this stock.'}), 404

    dividends = DividendPayment.query.filter_by(stock_id=stock_id, user_id=current_user.id)\
                                     .order_by(DividendPayment.pay_date.desc())\
                                     .all()
    return jsonify([dividend.to_dict() for dividend in dividends]), 200


# Update Dividend Payment
@dividends_bp.route('/dividends/<int:dividend_id>', methods=['PUT'])
@subscription_required('allow_dividend_tracking')
def update_dividend(current_user, dividend_id):
    dividend = DividendPayment.query.get(dividend_id)
    if not dividend:
        return jsonify({'error': 'Not found', 'details': 'Dividend payment not found.'}), 404
    
    if dividend.user_id != current_user.id: # Or check via stock.user_id if preferred
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to update this dividend payment.'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided for update.'}), 400

    errors = {}
    updated = False

    if 'amount' in data:
        amount_str = data['amount']
        try:
            amount = float(amount_str)
            if amount <= 0:
                errors['amount'] = 'Amount must be a positive number.'
            else:
                dividend.amount = amount
                updated = True
        except (ValueError, TypeError):
            errors['amount'] = 'Amount must be a valid number.'
            
    if 'pay_date' in data:
        pay_date_str = data['pay_date']
        try:
            if not isinstance(pay_date_str, str):
                raise ValueError("Date must be a string.")
            dividend.pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d').date()
            updated = True
        except ValueError:
            errors['pay_date'] = 'Invalid date format. Please use YYYY-MM-DD.'

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    
    if not updated:
        return jsonify({'message': 'No valid fields provided for update or values are the same.'}), 400

    db.session.commit()
    return jsonify(dividend.to_dict()), 200


# Delete Dividend Payment
@dividends_bp.route('/dividends/<int:dividend_id>', methods=['DELETE'])
@subscription_required('allow_dividend_tracking')
def delete_dividend(current_user, dividend_id):
    dividend = DividendPayment.query.get(dividend_id)
    if not dividend:
        return jsonify({'error': 'Not found', 'details': 'Dividend payment not found.'}), 404
    
    if dividend.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to delete this dividend payment.'}), 403

    db.session.delete(dividend)
    db.session.commit()
    return jsonify({'message': 'Dividend payment deleted successfully.'}), 200
