from flask import Blueprint, request, jsonify
from backend.models import User
from backend.app import db
import jwt # PyJWT
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash # Already imported in user.py but good for clarity

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Placeholder for JWT secret key, should be moved to config
SECRET_KEY = 'your_secret_key' # Replace with a strong, random key in production

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    errors = {}

    if not username:
        errors['username'] = 'Username is required.'
    elif not (3 <= len(username) <= 80):
        errors['username'] = 'Username must be between 3 and 80 characters.'

    if not email:
        errors['email'] = 'Email is required.'
    elif not (3 <= len(email) <= 120): # Basic length check for email
        errors['email'] = 'Email must be between 3 and 120 characters.'
    elif '@' not in email or '.' not in email.split('@')[-1]: # Basic email format
        errors['email'] = 'Invalid email format.'
    
    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters long.'
    
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Conflict', 'details': {'username': 'Username already exists.'}}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Conflict', 'details': {'email': 'Email already exists.'}}), 409

    new_user = User(username=username, email=email)
    new_user.set_password(password) 
    db.session.add(new_user)
    db.session.flush() # Flush to get new_user.id before commit for subscription

    # Assign default "Pro" plan with a 15-day trial
    from backend.models.subscription import SubscriptionPlan, UserSubscription 
    from datetime import timedelta # For trial period calculation
    
    pro_plan = SubscriptionPlan.query.filter_by(name="Pro").first() # Assuming "Pro" plan exists and is seeded
    if pro_plan:
        trial_end_date = datetime.utcnow() + timedelta(days=15)
        user_sub = UserSubscription(
            user_id=new_user.id,
            plan_id=pro_plan.id,
            status='trialing',
            trial_ends_at=trial_end_date
        )
        db.session.add(user_sub)
        print(f"User {new_user.id} assigned to 'Pro' plan trial ending on {trial_end_date.isoformat()}")
    else:
        # Fallback to "Free" plan if "Pro" is not found (should not happen if seeded)
        print(f"WARNING: 'Pro' subscription plan not found for new user {new_user.id}. Attempting to assign 'Free' plan.")
        free_plan = SubscriptionPlan.query.filter_by(name="Free").first()
        if free_plan:
            user_sub = UserSubscription(
                user_id=new_user.id,
                plan_id=free_plan.id,
                status='active'
            )
            db.session.add(user_sub)
            print(f"User {new_user.id} assigned to 'Free' plan as fallback.")
        else:
            print(f"CRITICAL WARNING: Neither 'Pro' nor 'Free' subscription plans found for new user {new_user.id}. User will not have a subscription.")
            # Consider rolling back user creation if a subscription is mandatory
            # db.session.rollback()
            # return jsonify({'error': 'Server Configuration Error', 'details': 'Default subscription plans not found.'}), 500

    db.session.commit()

    return jsonify({'message': 'User created successfully and Pro trial started.', 'user_id': new_user.id}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400
        
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Validation failed', 'details': {'credentials': 'Missing email or password.'}}), 400

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        # Generate JWT token
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token expires in 24 hours
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({'message': 'Login successful', 'access_token': token}), 200
    else:
        return jsonify({'error': 'Unauthorized', 'details': {'credentials': 'Invalid email or password.'}}), 401

# Optional: Token required decorator (example)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check for 'Authorization: Bearer <token>' first
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
        elif 'x-access-token' in request.headers: # Fallback to x-access-token
            token = request.headers['x-access-token']
        
        if not token:
            return jsonify({'error': 'Unauthorized', 'details': 'Token is missing!'}), 401
        
        try:
            jwt_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"]) # Renamed to jwt_data
            current_user = User.query.get(jwt_data['user_id'])
            if not current_user: 
                 return jsonify({'error': 'Unauthorized', 'details': 'User not found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Unauthorized', 'details': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Unauthorized', 'details': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @token_required # Apply token_required first to get current_user
    def decorated(current_user, *args, **kwargs): # current_user is passed by @token_required
        if current_user.id != 1: 
            return jsonify({'error': 'Forbidden', 'details': 'Admin access required.'}), 403
        return f(current_user, *args, **kwargs) 
    return decorated

def subscription_required(*feature_flags):
    def decorator(f):
        @wraps(f)
        @token_required # Ensures current_user is available and token is valid
        def decorated_function(current_user, *args, **kwargs):
            if not current_user.subscription:
                return jsonify({'error': 'Subscription Required', 'details': 'No active subscription found. Please subscribe to access this feature.'}), 403

            # Check subscription status and trial period
            is_active_sub = current_user.subscription.status in ['active', 'trialing']
            if not is_active_sub:
                return jsonify({'error': 'Subscription Required', 'details': 'Your subscription is not active. Please renew or subscribe.'}), 403

            if current_user.subscription.status == 'trialing':
                if current_user.subscription.trial_ends_at and current_user.subscription.trial_ends_at < datetime.utcnow():
                    # Update status to 'expired' or similar if trial ended (optional, could be a background job)
                    # For now, just deny access
                    return jsonify({'error': 'Subscription Required', 'details': 'Your trial period has ended. Please upgrade to a paid plan.'}), 403
            
            # Check feature flags against the user's plan
            plan = current_user.subscription.plan
            if not plan: # Should not happen if subscription exists and DB is consistent
                return jsonify({'error': 'Server Error', 'details': 'Subscription plan details not found.'}), 500

            missing_features = []
            for feature in feature_flags:
                if not hasattr(plan, feature) or not getattr(plan, feature):
                    missing_features.append(feature.replace("allow_", "").replace("_", " ")) # Make it more readable
            
            if missing_features:
                return jsonify({
                    'error': 'Upgrade Required', 
                    'details': f"Your current plan '{plan.name}' does not allow access to: {', '.join(missing_features)}. Please upgrade your plan."
                }), 403
            
            return f(current_user, *args, **kwargs)
        return decorated_function
    return decorator
