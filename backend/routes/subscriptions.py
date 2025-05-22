from flask import Blueprint, jsonify
from backend.models import SubscriptionPlan

subscriptions_bp = Blueprint('subscriptions', __name__, url_prefix='/api/subscription-plans')

@subscriptions_bp.route('', methods=['GET'])
def list_public_subscription_plans():
    """
    Public endpoint to list all available (public) subscription plans.
    """
    try:
        plans = SubscriptionPlan.query.filter_by(is_public=True).order_by(SubscriptionPlan.price_monthly).all()
        plans_data = [plan.to_dict() for plan in plans]
        return jsonify(plans_data), 200
    except Exception as e:
        print(f"Error fetching subscription plans: {e}")
        return jsonify({'error': 'Server Error', 'details': 'Could not retrieve subscription plans.'}), 500
