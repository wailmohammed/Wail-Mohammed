from flask import Blueprint, jsonify
from backend.routes.auth import token_required
from backend.models import UserSubscription # To help with type hinting or direct access if needed

user_bp = Blueprint('user', __name__, url_prefix='/api/users')

@user_bp.route('/me/subscription', methods=['GET'])
@token_required
def get_my_subscription(current_user):
    """
    Returns the current authenticated user's subscription details.
    """
    if not current_user.subscription:
        # This case might happen if a user was created before subscription logic
        # or if somehow the default subscription assignment failed.
        return jsonify({'error': 'Not found', 'details': 'No subscription information found for this user.'}), 404

    # The User.subscription relationship is lazy='joined', so plan details should be loaded.
    # We can call to_dict() on both subscription and its plan.
    subscription_data = current_user.subscription.to_dict()
    # Ensure plan details are included if not already by to_dict() or if more control is needed.
    if current_user.subscription.plan:
        subscription_data['plan_details'] = current_user.subscription.plan.to_dict()
    else: # Should ideally not happen if DB is consistent
        subscription_data['plan_details'] = None
        print(f"Warning: User {current_user.id} has a subscription (ID: {current_user.subscription.id}) but no associated plan details.")


    return jsonify(subscription_data), 200
