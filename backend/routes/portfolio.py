from flask import Blueprint, request, jsonify
from backend.models import Stock, User, db # db was already imported, User is not directly used here but good for context
from backend.routes.auth import token_required, subscription_required # Import the new decorator
from datetime import datetime

# Endpoint to Add Stock
@portfolio_bp.route('/stocks', methods=['POST'])
@subscription_required('allow_csv_import') # Placeholder, actual logic based on number of stocks
def add_stock(current_user):
    # Max stocks check
    plan = current_user.subscription.plan
    if plan.max_stocks is not None:
        current_stock_count = Stock.query.filter_by(user_id=current_user.id).count()
        if current_stock_count >= plan.max_stocks:
            return jsonify({
                'error': 'Limit Reached', 
                'details': f"Your current plan '{plan.name}' allows a maximum of {plan.max_stocks} stocks. You have {current_stock_count}."
            }), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    errors = {}
    symbol = data.get('symbol')
    shares_str = data.get('shares') # Get as string first for validation
    purchase_price_str = data.get('purchase_price') # Get as string
    purchase_date_str = data.get('purchase_date') 
    sector_manual = data.get('sector')
    custom_category = data.get('custom_category') # New: custom_category

    # Validate symbol
    if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
        errors['symbol'] = 'Symbol is required and must be a string between 1 and 20 characters.'
    
    # Validate shares
    shares = None
    if shares_str is None: # Check for presence before type
        errors['shares'] = 'Shares are required.'
    else:
        try:
            shares = int(shares_str)
            if shares <= 0:
                errors['shares'] = 'Shares must be a positive integer.'
        except (ValueError, TypeError):
            errors['shares'] = 'Shares must be a valid integer.'

    # Validate purchase_price
    purchase_price = None
    if purchase_price_str is None: # Check for presence
        errors['purchase_price'] = 'Purchase price is required.'
    else:
        try:
            purchase_price = float(purchase_price_str)
            if purchase_price <= 0:
                errors['purchase_price'] = 'Purchase price must be a positive number.'
        except (ValueError, TypeError):
            errors['purchase_price'] = 'Purchase price must be a valid number.'

    # Validate sector (optional, but if provided, check length)
    if sector_manual is not None and (not isinstance(sector_manual, str) or len(sector_manual) > 100):
        errors['sector'] = 'Sector must be a string with a maximum length of 100 characters.'

    # Validate custom_category (optional, but if provided, check length)
    # Apply subscription check for custom_category
    if custom_category is not None:
        if not plan.allow_custom_categories:
             return jsonify({'error': 'Upgrade Required', 'details': f"Your plan '{plan.name}' does not allow custom categories."}), 403
        if not isinstance(custom_category, str) or len(custom_category) > 100:
            errors['custom_category'] = 'Custom category must be a string with a maximum length of 100 characters.'
    
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Sector fetching logic (remains largely the same, but uses validated symbol)
    fetched_sector = None
    try:
        # get_stock_price now returns a dict with price and sector
        # We are primarily interested in the sector here if not provided manually.
        # If sector_manual is provided, this call could be skipped or used for validation only.
        stock_data_from_service = get_stock_price(symbol.upper()) # This calls get_company_overview internally
        if stock_data_from_service and stock_data_from_service.get('sector'):
            fetched_sector = stock_data_from_service['sector']
    except AlphaVantageError as e:
        print(f"Note: Could not fetch live sector for {symbol.upper()} during add: {e}")
    except Exception as e:
        print(f"Unexpected error fetching live sector for {symbol.upper()} during add: {e}")


    final_sector = sector_manual if sector_manual else fetched_sector
    if not final_sector or final_sector == "Unknown": # If still no sector, set to "Uncategorized"
        final_sector = "Uncategorized"


    purchase_date = None
    if purchase_date_str:
        # More robust date parsing can be added here if needed, for now, keeping existing.
        # The frontend sends ISO string, so fromisoformat should be fine.
        try:
            # Ensure it's a string before trying to parse
            if not isinstance(purchase_date_str, str):
                 raise ValueError("Date must be a string.")
            purchase_date = datetime.fromisoformat(purchase_date_str.replace('Z', '+00:00'))
        except ValueError:
             # Try other common formats as fallback or return specific error
            date_formats_to_try = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
            parsed_date_success = False
            for fmt in date_formats_to_try:
                try:
                    purchase_date = datetime.strptime(purchase_date_str, fmt)
                    parsed_date_success = True
                    break
                except (ValueError, TypeError): # TypeError if purchase_date_str is not string
                    continue
            if not parsed_date_success:
                return jsonify({'error': 'Validation failed', 'details': {'purchase_date': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ), YYYY-MM-DD HH:MM:SS, or YYYY-MM-DD.'}}), 400
    else:
        purchase_date = datetime.utcnow() 

    new_stock = Stock(
        user_id=current_user.id,
        symbol=symbol.upper(),
        shares=shares,
        purchase_price=purchase_price,
        purchase_date=purchase_date,
        sector=final_sector, 
        custom_category=custom_category.strip() if custom_category else None # Save custom_category
    )
    db.session.add(new_stock)
    db.session.commit()

    return jsonify({
        'id': new_stock.id,
        'user_id': new_stock.user_id,
        'symbol': new_stock.symbol,
        'shares': new_stock.shares,
        'purchase_price': new_stock.purchase_price,
        'purchase_date': new_stock.purchase_date.isoformat(),
        'sector': new_stock.sector,
        'custom_category': new_stock.custom_category # Include custom_category in response
    }), 201

from backend.services.financial_data import get_stock_price, get_company_overview, AlphaVantageError # Import the service

# Endpoint to View Portfolio
@portfolio_bp.route('/stocks', methods=['GET'])
@token_required
def view_portfolio(current_user):
    search_term = request.args.get('search', None)
    filter_letter = request.args.get('filter_by_letter', None)

    query = Stock.query.filter_by(user_id=current_user.id)

    if search_term:
        query = query.filter(Stock.symbol.ilike(f"%{search_term}%"))
    
    if filter_letter:
        # Ensure it's a single character, and a letter.
        if len(filter_letter) == 1 and filter_letter.isalpha():
            query = query.filter(Stock.symbol.ilike(f"{filter_letter}%"))
        else:
            # Optional: return a 400 error if filter_by_letter is invalid
            # return jsonify({'message': 'Invalid filter_by_letter parameter. Must be a single letter.'}), 400
            pass # Or simply ignore invalid filter_by_letter

    stocks = query.order_by(Stock.symbol).all()
    
    portfolio_data = []
    for stock in stocks:
        current_price = None
        market_value = None
        price_error = None
        
        # TODO: For production, implement more robust caching and potentially batching for API calls.
        # The current simple cache in get_stock_price (for price) and get_company_overview (for sector) helps.
        try:
            # get_stock_price now returns a dict: {"price": ..., "sector": ...}
            price_data = get_stock_price(stock.symbol) 
            if price_data and price_data.get('price') is not None:
                current_price = price_data['price']
                market_value = round(stock.shares * current_price, 2)
                
                # Auto-update sector if it's missing or "Uncategorized" and we get a valid one from API
                if (not stock.sector or stock.sector == "Uncategorized") and price_data.get('sector') and price_data.get('sector') != "Unknown":
                    stock.sector = price_data['sector']
                    db.session.add(stock) # Add to session to be committed later if view_portfolio does a commit
                                          # For now, this change might not persist unless a commit happens.
                                          # A better approach for auto-update would be a background job or explicit user action.
                                          # For this task, we'll focus on the allocation endpoint using existing sectors.

            else: # Price data or price itself is None
                 current_price = None # Ensure current_price is None if not fetched
                 market_value = None  # Ensure market_value is None if not fetched

        except AlphaVantageError as e:
            print(f"AlphaVantage API Error for {stock.symbol}: {e}")
            current_price = None # Ensure current_price is None on error
            market_value = None  # Ensure market_value is None on error
            price_error = str(e)
        except Exception as e: # Catch any other unexpected error during price fetching
            print(f"Unexpected error fetching price for {stock.symbol}: {e}")
            price_error = "An unexpected error occurred while fetching price."

        portfolio_data.append({
            'id': stock.id,
            'symbol': stock.symbol,
            'shares': stock.shares,
            'purchase_price': stock.purchase_price,
            'purchase_date': stock.purchase_date.isoformat(),
            'current_price': current_price,
            'market_value': market_value,
            'sector': stock.sector, 
            'custom_category': stock.custom_category, 
            'total_dividends_received': sum(dp.amount for dp in stock.dividend_payments), # Calculate total dividends
            'price_error': price_error 
        })
    
    # db.session.commit() # If we were auto-updating sectors and wanted to persist immediately.
    # For now, view_portfolio is read-only regarding sector updates from API.
        
    return jsonify(portfolio_data), 200

# Endpoint to Update Stock
@portfolio_bp.route('/stocks/<int:stock_id>', methods=['PUT'])
@token_required # Basic token is enough, specific feature checks inside if custom_category is modified
def update_stock(current_user, stock_id):
    stock = Stock.query.get(stock_id) 
    if not stock:
        return jsonify({'error': 'Not found', 'details': 'Stock not found.'}), 404
    
    if stock.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to update this stock.'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided for update.'}), 400

    errors = {}
    updated = False

    if 'shares' in data:
        shares_str = data['shares']
        try:
            shares = int(shares_str)
            if shares <= 0:
                errors['shares'] = 'Shares must be a positive integer.'
            else:
                stock.shares = shares
                updated = True
        except (ValueError, TypeError):
            errors['shares'] = 'Shares must be a valid integer.'
    
    if 'purchase_price' in data:
        purchase_price_str = data['purchase_price']
        try:
            purchase_price = float(purchase_price_str)
            if purchase_price <= 0:
                errors['purchase_price'] = 'Purchase price must be a positive number.'
            else:
                stock.purchase_price = purchase_price
                updated = True
        except (ValueError, TypeError):
            errors['purchase_price'] = 'Purchase price must be a valid number.'
    
    if 'sector' in data:
        sector_manual = data.get('sector') 
        if sector_manual is not None: 
            if isinstance(sector_manual, str) and 0 < len(sector_manual.strip()) <= 100:
                stock.sector = sector_manual.strip()
            elif isinstance(sector_manual, str) and len(sector_manual.strip()) == 0: 
                 stock.sector = "Uncategorized"
            else: 
                errors['sector'] = 'Sector must be a string with a maximum length of 100 characters.'
            if 'sector' not in errors: updated = True
        
    if 'custom_category' in data:
        custom_category_val = data.get('custom_category')
        if custom_category_val is not None: 
            # Check subscription for custom_category if user is trying to set/change it
            if not current_user.subscription.plan.allow_custom_categories:
                return jsonify({'error': 'Upgrade Required', 'details': f"Your plan '{current_user.subscription.plan.name}' does not allow custom categories."}), 403
            
            if isinstance(custom_category_val, str) and len(custom_category_val.strip()) <= 100:
                stock.custom_category = custom_category_val.strip() if custom_category_val.strip() else None
                updated = True
            else: 
                errors['custom_category'] = 'Custom category must be a string with a maximum length of 100 characters.'
        


    if 'purchase_date' in data:
        purchase_date_str = data.get('purchase_date')
        if purchase_date_str:
            try:
                if not isinstance(purchase_date_str, str):
                    raise ValueError("Date must be a string.")
                stock.purchase_date = datetime.fromisoformat(purchase_date_str.replace('Z', '+00:00'))
                updated = True
            except ValueError:
                # Try other common formats as fallback
                parsed_date_success_update = False
                date_formats_to_try_update = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
                for fmt in date_formats_to_try_update:
                    try:
                        stock.purchase_date = datetime.strptime(purchase_date_str, fmt)
                        parsed_date_success_update = True
                        updated = True
                        break
                    except (ValueError, TypeError):
                        continue
                if not parsed_date_success_update:
                     errors['purchase_date'] = 'Invalid date format. Use ISO (YYYY-MM-DDTHH:MM:SSZ), YYYY-MM-DD HH:MM:SS, or YYYY-MM-DD.'
        # If purchase_date is explicitly null or empty string in data, it could mean "don't update" or "clear it"
        # Current logic: only updates if a valid date string is provided. No change if key missing or empty.

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    
    if not updated:
        return jsonify({'message': 'No valid fields provided for update or values are the same.'}), 400 # Or 200 if no change is OK

    db.session.commit()
    return jsonify({
        'id': stock.id,
        'symbol': stock.symbol,
        'shares': stock.shares,
        'purchase_price': stock.purchase_price,
        'purchase_date': stock.purchase_date.isoformat(),
        'sector': stock.sector, 
        'custom_category': stock.custom_category, # Include custom_category in response
        'message': 'Stock updated successfully'
    }), 200

# Endpoint to Delete Stock
@portfolio_bp.route('/stocks/<int:stock_id>', methods=['DELETE'])
@token_required
def delete_stock(current_user, stock_id):
    stock = Stock.query.get(stock_id) # Use get for manual check
    if not stock:
        return jsonify({'error': 'Not found', 'details': 'Stock not found.'}), 404
    if stock.user_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'details': 'Unauthorized to delete this stock.'}), 403

    db.session.delete(stock)
    db.session.commit()
    return jsonify({'message': 'Stock deleted successfully'}), 200 # Or 204 No Content, but message is fine

# Endpoint to Get Stock Historical Data
@portfolio_bp.route('/stocks/<string:symbol>/history', methods=['GET'])
@token_required # Ensure user is logged in, though symbol is the main driver here
def get_stock_history(current_user, symbol):
    if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
        return jsonify({'error': 'Validation failed', 'details': {'symbol':'Stock symbol is required and must be a string between 1 and 20 characters.'}}), 400
    
    try:
        historical_data = get_historical_data(symbol.upper()) # Service function call
        if historical_data is None:
            # This can occur if AlphaVantage returns no data for the symbol (e.g. invalid symbol)
            # or if the API key is invalid/limit reached and service handles it by returning None.
            return jsonify({'error': 'Not found', 'details': f'Could not retrieve historical data for {symbol.upper()}. Symbol might be invalid or data unavailable.'}), 404
        
        return jsonify(historical_data), 200
        
    except AlphaVantageError as e:
        # Specific error from our service layer for AlphaVantage issues
        return jsonify({'error': 'API Error', 'details': f"Error fetching historical data for {symbol.upper()}: {str(e)}"}), 503 # Service Unavailable
    except Exception as e:
        # Catch-all for other unexpected errors
        print(f"Unexpected error in get_stock_history for {symbol}: {e}") # Log for server diagnosis
        return jsonify({'error': 'Server Error', 'details': f"An unexpected error occurred."}), 500

# Portfolio Allocation Endpoint
@portfolio_bp.route('/allocation', methods=['GET'])
@subscription_required('allow_benchmarking') # Assuming allocation is part of benchmarking/advanced features
def get_portfolio_allocation(current_user):
    stocks = Stock.query.filter_by(user_id=current_user.id).all()
    
    sector_allocation = {}
    total_portfolio_market_value = 0.0

    for stock in stocks:
        current_price = None
        market_value = 0.0 # Default to 0 if price not found
        
        try:
            price_data = get_stock_price(stock.symbol) # Returns {"price": ..., "sector": ...}
            if price_data and price_data.get('price') is not None:
                current_price = price_data['price']
                market_value = stock.shares * current_price
                
                # Auto-update sector if missing and fetched from API
                # This is more of a side-effect here, consider if this is the right place.
                # For allocation, we use the sector currently in DB.
                if (not stock.sector or stock.sector == "Uncategorized") and price_data.get('sector') and price_data.get('sector') != "Unknown":
                    # This change won't be persisted unless a commit happens.
                    # For allocation, it's better to rely on already stored sector or one fetched just for this request.
                    # Let's use the DB sector, and if it's uncat, try to use the fetched one for this calculation only.
                    pass # Not updating DB here.

            else: # Price data or price itself is None
                 print(f"Warning: Could not fetch price for {stock.symbol} for allocation calculation.")

        except AlphaVantageError as e:
            print(f"AlphaVantage API Error for {stock.symbol} during allocation: {e}")
        except Exception as e:
            print(f"Unexpected error fetching price for {stock.symbol} during allocation: {e}")

        sector_name = stock.sector if stock.sector and stock.sector != "Unknown" else "Uncategorized"
        
        # If sector is still "Uncategorized" from DB, try to use a freshly fetched one if available
        if sector_name == "Uncategorized" and price_data and price_data.get('sector') and price_data.get('sector') != "Unknown":
            sector_name = price_data['sector']

        sector_allocation[sector_name] = sector_allocation.get(sector_name, 0.0) + market_value
        total_portfolio_market_value += market_value

    # Prepare data for pie chart (name, value structure)
    # And also calculate percentages
    allocation_summary = []
    if total_portfolio_market_value > 0: # Avoid division by zero
        for sector, value in sector_allocation.items():
            percentage = round((value / total_portfolio_market_value) * 100, 2)
            allocation_summary.append({
                "name": sector, # Sector name
                "value": round(value, 2), # Total market value for this sector
                "percentage": percentage
            })
    else: # Handle case of zero total value (e.g. all prices are None)
         for sector, value in sector_allocation.items():
            allocation_summary.append({
                "name": sector,
                "value": round(value, 2),
                "percentage": 0.0
            })
            
    # Sort by value descending for better chart display
    allocation_summary.sort(key=lambda x: x['value'], reverse=True)
            
    return jsonify({
        "total_portfolio_value": round(total_portfolio_market_value, 2),
        "allocation": allocation_summary
    }), 200


import csv
import io # For reading the file stream as text
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@portfolio_bp.route('/upload_csv', methods=['POST'])
@subscription_required('allow_csv_import')
def upload_csv(current_user):
    # Max stocks check before processing CSV
    plan = current_user.subscription.plan
    if plan.max_stocks is not None:
        current_stock_count = Stock.query.filter_by(user_id=current_user.id).count()
        # This is a simplification. A more accurate check would be current_stock_count + potential_csv_rows > max_stocks
        # However, parsing the CSV first to count rows before checking is more complex.
        # For now, if they are already at their limit, they can't upload more.
        if current_stock_count >= plan.max_stocks:
            return jsonify({
                'error': 'Limit Reached',
                'details': f"Your current plan '{plan.name}' allows {plan.max_stocks} stocks. You have {current_stock_count}. CSV upload aborted."
            }), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Bad Request', 'details': 'No file part in the request.'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Bad Request', 'details': 'No selected file.'}), 400
        
    if not file or not allowed_file(file.filename): # allowed_file checks for .csv extension
        return jsonify({'error': 'Bad Request', 'details': 'Invalid file type. Please upload a CSV file.'}), 400

    # filename = secure_filename(file.filename) # Already done, but good to remember it's used.
    # No need to store filename on server for this implementation.

    imported_count = 0
    error_list = []
    
    try:
        # Read the file stream as text. file.stream is a SpooledTemporaryFile.
        # We need to decode it as UTF-8 (common for CSVs).
        stream = io.TextIOWrapper(file.stream, encoding='utf-8', newline='')
        csv_reader = csv.DictReader(stream) # Use DictReader for header-based column access
        
        # Check for expected headers (case-insensitive check for flexibility)
        expected_headers = {'symbol', 'shares', 'purchaseprice', 'purchasedate'}
        actual_headers_lower = {header.lower().replace(' ', '') for header in csv_reader.fieldnames or []}

        missing_headers = list(expected_headers - actual_headers_lower) # expected_headers is defined
        if missing_headers:
            return jsonify({'error': 'Bad Request', 'details': f"Missing required CSV headers: {', '.join(sorted(list(missing_headers)))}. Expected: Symbol, Shares, PurchasePrice, PurchaseDate"}), 400

        # Use a list to collect new Stock objects for bulk insert if all rows are valid
        stocks_to_add = []

        for row_number, row in enumerate(csv_reader, start=2): # start=2 because 1 is header
            # Helper to get values from row (case-insensitive for keys)
            def get_row_value(field_name_options):
                for name_option in field_name_options:
                    if name_option in row:
                        return row[name_option]
                # Try case-insensitive match as a fallback if original fieldnames were mixed case
                for key, val in row.items():
                    if key.lower().replace(' ', '') in [opt.lower().replace(' ', '') for opt in field_name_options]:
                        return val
                return None

            symbol = get_row_value(['Symbol', 'symbol'])
            shares_str = get_row_value(['Shares', 'shares'])
            purchase_price_str = get_row_value(['PurchasePrice', 'purchaseprice', 'Purchase Price'])
            purchase_date_str = get_row_value(['PurchaseDate', 'purchasedate', 'Purchase Date'])

            # Validate data for each row
            symbol = get_row_value(['Symbol', 'symbol'])
            shares_str = get_row_value(['Shares', 'shares'])
            purchase_price_str = get_row_value(['PurchasePrice', 'purchaseprice', 'Purchase Price'])
            purchase_date_str = get_row_value(['PurchaseDate', 'purchasedate', 'Purchase Date'])
            # Sector is not part of CSV import for now, will be auto-fetched or Uncategorized.

            row_errors = {}
            if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
                row_errors['symbol'] = 'Symbol is required and must be a string (1-20 chars).'
            
            current_row_shares = None
            if shares_str is None:
                 row_errors['shares'] = 'Shares are required.'
            else:
                try:
                    current_row_shares = int(shares_str)
                    if current_row_shares <= 0:
                        row_errors['shares'] = 'Shares must be positive.'
                except (ValueError, TypeError):
                    row_errors['shares'] = 'Shares must be a valid integer.'

            current_row_purchase_price = None
            if purchase_price_str is None:
                row_errors['purchase_price'] = 'Purchase price is required.'
            else:
                try:
                    current_row_purchase_price = float(purchase_price_str)
                    if current_row_purchase_price <= 0:
                        row_errors['purchase_price'] = 'Purchase price must be positive.'
                except (ValueError, TypeError):
                    row_errors['purchase_price'] = 'Purchase price must be a valid number.'
            
            current_row_purchase_date = None
            if not purchase_date_str:
                row_errors['purchase_date'] = 'Purchase date is required.'
            else:
                parsed_date_success_csv = False
                for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y']:
                    try:
                        current_row_purchase_date = datetime.strptime(purchase_date_str, fmt)
                        parsed_date_success_csv = True
                        break
                    except (ValueError, TypeError):
                        continue
                if not parsed_date_success_csv:
                    row_errors['purchase_date'] = f"Invalid date format '{purchase_date_str}'. Use YYYY-MM-DD or MM/DD/YYYY."

            if row_errors:
                error_list.append({'row': row_number, 'errors': row_errors, 'data': dict(row) if row else {}}) # Include row data for context
                continue # Skip this row, collect all errors

            # If row is valid, create Stock object (without adding to session yet)
            # Sector fetching logic
            final_row_sector = "Uncategorized" # Default
            if symbol: # Only fetch if symbol is valid from row
                try:
                    stock_data_from_service_csv = get_stock_price(symbol.upper()) 
                    if stock_data_from_service_csv and stock_data_from_service_csv.get('sector'):
                        final_row_sector = stock_data_from_service_csv['sector']
                        if final_row_sector == "Unknown": final_row_sector = "Uncategorized"
                except Exception as e: # Catch broad exceptions from service call during CSV processing
                    print(f"CSV Import: Could not fetch sector for {symbol} (Row {row_number}): {e}")
            
            stocks_to_add.append(Stock(
                user_id=current_user.id, symbol=symbol.upper(), shares=current_row_shares,
                purchase_price=current_row_purchase_price, purchase_date=current_row_purchase_date,
                sector=final_row_sector
            ))
        
        if error_list: 
             return jsonify({
                'error': 'Validation failed during CSV processing', 
                'details': 'Some rows had errors. No stocks were imported.',
                'row_errors': error_list, # Detailed errors per row
                'imported_count': 0 
            }), 422 
        else:
            db.session.add_all(stocks_to_add) # Bulk add
            db.session.commit()
            return jsonify({
                'message': f'CSV imported successfully. {len(stocks_to_add)} stocks added.',
                'imported_count': len(stocks_to_add),
                'errors': []
            }), 201

    except UnicodeDecodeError:
        return jsonify({'error': 'Bad Request', 'details': 'Error decoding file. Please ensure the file is UTF-8 encoded.'}), 400
    except csv.Error as e: 
        return jsonify({'error': 'Bad Request', 'details': f'Error reading CSV file: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback() # Rollback on unexpected errors during processing
        print(f"Unexpected error during CSV upload: {e}") 
        return jsonify({'error': 'Server Error', 'details': f'An unexpected error occurred: {str(e)}'}), 500

# News Endpoint (Public - No token required)
@portfolio_bp.route('/news', methods=['GET'])
def get_financial_news_route():
    # Query parameters for more flexibility, e.g., /api/news?topics=technology,earnings&limit=10
    topics_str = request.args.get('topics')
    tickers_str = request.args.get('tickers')
    limit = request.args.get('limit', default=10, type=int)

    topics = topics_str.split(',') if topics_str else None
    tickers = tickers_str.split(',') if tickers_str else None
    
    # Cap limit to a reasonable number for public endpoint
    if limit > 50: 
        limit = 50

    try:
        news_items = get_latest_financial_news(topics=topics, tickers=tickers, limit=limit)
        if news_items is None: # Should ideally not happen if service handles errors and returns []
            return jsonify({'message': 'Could not retrieve news at this time.', 'news': []}), 500
        return jsonify({'news': news_items}), 200
    except AlphaVantageError as e:
        # Log the error for server-side diagnosis
        print(f"AlphaVantage API Error in /api/news: {e}")
        # Return a user-friendly message; avoid exposing raw error details from AlphaVantageError directly if sensitive
        return jsonify({'message': f"Failed to fetch news due to an API issue: {str(e)}", 'news': []}), 503 # Service Unavailable
    except Exception as e:
        print(f"Unexpected error in /api/news: {e}")
        return jsonify({'message': 'An unexpected error occurred while fetching news.', 'news': []}), 500


# Generic JSON Import Endpoint
@portfolio_bp.route('/import_generic_json', methods=['POST'])
@subscription_required('allow_generic_import')
def import_generic_json(current_user):
    """
    Imports portfolio data from a standardized JSON format.
    The JSON can contain 'holdings' and/or 'transactions'.

    JSON Format Example:
    {
      "holdings": [
        {
          "symbol": "AAPL",
          "shares": 10,
          "average_cost_price": 150.00, // Used as purchase_price for new/updated stock
          "sector": "Technology", // Optional
          "custom_category": "Growth" // Optional
        }
      ],
      "transactions": [ 
        {
          "symbol": "MSFT",
          "shares": 5,
          "price": 200.00, // Purchase price for this lot
          "transaction_type": "buy", 
          "transaction_date": "YYYY-MM-DD", // Purchase date for this lot
          "sector": "Technology", // Optional
          "custom_category": "Core Holding" // Optional
        }
      ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request', 'details': 'No JSON data provided.'}), 400

    holdings_data = data.get('holdings', [])
    transactions_data = data.get('transactions', [])

    if not isinstance(holdings_data, list) or not isinstance(transactions_data, list):
        return jsonify({'error': 'Validation failed', 'details': {'structure': 'Holdings and transactions must be lists.'}}), 400

    processed_holdings_count = 0
    processed_transactions_count = 0
    item_errors = [] # Collect errors for individual items
    
    plan = current_user.subscription.plan
    
    # Use a list to collect new/updated Stock objects for bulk processing if all validations pass
    stocks_to_process = [] 
    
    # --- Validate Holdings ---
    for idx, item in enumerate(holdings_data):
        current_stock_count = Stock.query.filter_by(user_id=current_user.id).count() + \
                              len([s for s in stocks_to_process if s.get('_is_new', False)]) # Count existing + new ones in this batch
        
        symbol = item.get('symbol')
        existing_stock_check = Stock.query.filter_by(user_id=current_user.id, symbol=symbol.upper() if symbol else None).first()
        
        if plan.max_stocks is not None and current_stock_count >= plan.max_stocks and not existing_stock_check:
            item_errors.append({'item_type': 'holding', 'index': idx, 'symbol': symbol, 'error': f"Stock limit of {plan.max_stocks} reached."})
            continue

        shares_str = item.get('shares')
        avg_cost_price_str = item.get('average_cost_price')
        sector = item.get('sector')
        custom_category = item.get('custom_category')
        
        current_item_validation_errors = {}
        if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
            current_item_validation_errors['symbol'] = 'Symbol is required (string, 1-20 chars).'
        
        shares = None
        if shares_str is None: current_item_validation_errors['shares'] = 'Shares are required.'
        else:
            try: shares = int(shares_str); assert shares > 0
            except: current_item_validation_errors['shares'] = 'Shares must be a positive integer.'
        
        avg_cost_price = None
        if avg_cost_price_str is None: current_item_validation_errors['average_cost_price'] = 'Average cost price is required.'
        else:
            try: avg_cost_price = float(avg_cost_price_str); assert avg_cost_price > 0
            except: current_item_validation_errors['average_cost_price'] = 'Average cost price must be a positive number.'

        if sector is not None and (not isinstance(sector, str) or len(sector) > 100):
            current_item_validation_errors['sector'] = 'Sector must be a string (max 100 chars).'
        if custom_category is not None:
            if not plan.allow_custom_categories:
                 current_item_validation_errors['custom_category'] = f"Your plan '{plan.name}' does not allow custom categories."
            elif not isinstance(custom_category, str) or len(custom_category) > 100:
                 current_item_validation_errors['custom_category'] = 'Custom category must be a string (max 100 chars).'

        if current_item_validation_errors:
            item_errors.append({'item_type': 'holding', 'index': idx, 'symbol': symbol, 'details': current_item_validation_errors})
            continue
        
        stocks_to_process.append({
            '_operation': 'upsert_holding', '_is_new': not existing_stock_check,
            'symbol': symbol.upper(), 'shares': shares, 'average_cost_price': avg_cost_price,
            'sector': sector, 'custom_category': custom_category
        })

    # --- Validate Transactions ---
    for idx, trans in enumerate(transactions_data):
        current_stock_count = Stock.query.filter_by(user_id=current_user.id).count() + \
                              len([s for s in stocks_to_process if s.get('_is_new', False)])
        
        symbol = trans.get('symbol')
        existing_stock_check_tx = Stock.query.filter_by(user_id=current_user.id, symbol=symbol.upper() if symbol else None).first() or \
                                  any(s['symbol'] == symbol.upper() for s in stocks_to_process if s['symbol'])

        if plan.max_stocks is not None and current_stock_count >= plan.max_stocks and not existing_stock_check_tx:
            item_errors.append({'item_type': 'transaction', 'index': idx, 'symbol': symbol, 'error': f"Stock limit of {plan.max_stocks} reached."})
            continue

        shares_str = trans.get('shares')
        price_str = trans.get('price')
        tx_type = trans.get('transaction_type', '').lower()
        tx_date_str = trans.get('transaction_date')
        sector = trans.get('sector')
        custom_category = trans.get('custom_category')

        current_item_validation_errors = {}
        if not symbol or not isinstance(symbol, str) or not (1 <= len(symbol) <= 20):
            current_item_validation_errors['symbol'] = 'Symbol is required (string, 1-20 chars).'
        
        shares = None
        if shares_str is None: current_item_validation_errors['shares'] = 'Shares are required.'
        else:
            try: shares = int(shares_str); assert shares > 0
            except: current_item_validation_errors['shares'] = 'Shares must be a positive integer.'

        price = None
        if price_str is None: current_item_validation_errors['price'] = 'Price is required.'
        else:
            try: price = float(price_str); assert price > 0
            except: current_item_validation_errors['price'] = 'Price must be a valid number.'

        if tx_type not in ['buy', 'sell']:
            current_item_validation_errors['transaction_type'] = "Transaction type must be 'buy' or 'sell'."
        
        tx_date = None
        if not tx_date_str: current_item_validation_errors['transaction_date'] = 'Transaction date is required.'
        else:
            try: tx_date = datetime.strptime(tx_date_str, '%Y-%m-%d').date()
            except: current_item_validation_errors['transaction_date'] = 'Invalid date format (YYYY-MM-DD required).'
        
        if sector is not None and (not isinstance(sector, str) or len(sector) > 100):
            current_item_validation_errors['sector'] = 'Sector must be a string (max 100 chars).'
        if custom_category is not None:
            if not plan.allow_custom_categories:
                 current_item_validation_errors['custom_category'] = f"Your plan '{plan.name}' does not allow custom categories."
            elif not isinstance(custom_category, str) or len(custom_category) > 100:
                 current_item_validation_errors['custom_category'] = 'Custom category must be a string (max 100 chars).'

        if current_item_validation_errors:
            item_errors.append({'item_type': 'transaction', 'index': idx, 'symbol': symbol, 'details': current_item_validation_errors})
            continue

        if tx_type == 'buy':
            stocks_to_process.append({
                '_operation': 'buy_transaction', '_is_new': not existing_stock_check_tx,
                'symbol': symbol.upper(), 'shares': shares, 'price': price, 'transaction_date': tx_date,
                'sector': sector, 'custom_category': custom_category
            })
        elif tx_type == 'sell':
            # Basic validation for sell: check if stock exists to sell from
            if not existing_stock_check_tx:
                item_errors.append({'item_type': 'transaction', 'index': idx, 'symbol': symbol, 'error': 'Cannot sell stock that does not exist in portfolio or batch.'})
                continue
            stocks_to_process.append({
                '_operation': 'sell_transaction', # Process sell if needed later
                'symbol': symbol.upper(), 'shares': shares, 'price': price, 'transaction_date': tx_date
            })


    if item_errors: # If any validation errors occurred during item processing
        return jsonify({
            'error': 'Import failed due to item validation errors', 
            'details': 'One or more items in the JSON had errors. No data was imported.',
            'item_errors': item_errors,
        }), 422
    
    # --- If all validations pass, proceed with DB operations ---
    try:
        for item_data in stocks_to_process:
            op = item_data['_operation']
            symbol = item_data['symbol']
            
            if op == 'upsert_holding':
                stock = Stock.query.filter_by(user_id=current_user.id, symbol=symbol).first()
                if stock: # Update
                    stock.shares = item_data['shares']
                    stock.purchase_price = item_data['average_cost_price']
                    stock.purchase_date = datetime.utcnow() # Reset purchase date for simplicity
                    if item_data['sector']: stock.sector = item_data['sector']
                    if item_data['custom_category'] is not None: 
                        stock.custom_category = item_data['custom_category'] if item_data['custom_category'] else None
                else: # Create new
                    final_sector = item_data['sector']
                    if not final_sector:
                        try: overview = get_company_overview(symbol); final_sector = (overview.get('sector') if overview else "Uncategorized")
                        except: final_sector = "Uncategorized"
                    stock = Stock(user_id=current_user.id, symbol=symbol, shares=item_data['shares'],
                                  purchase_price=item_data['average_cost_price'], purchase_date=datetime.utcnow(),
                                  sector=final_sector, custom_category=item_data['custom_category'] if item_data['custom_category'] else None)
                    db.session.add(stock)
                processed_holdings_count += 1
            
            elif op == 'buy_transaction':
                stock = Stock.query.filter_by(user_id=current_user.id, symbol=symbol).first()
                if stock: # Add to existing
                    stock.shares += item_data['shares']
                    # Not recalculating average cost for simplicity. Could update purchase_date if needed.
                    if item_data['sector']: stock.sector = item_data['sector']
                    if item_data['custom_category'] is not None: stock.custom_category = item_data['custom_category'] if item_data['custom_category'] else None
                else: # Create new
                    final_sector = item_data['sector']
                    if not final_sector:
                        try: overview = get_company_overview(symbol); final_sector = (overview.get('sector') if overview else "Uncategorized")
                        except: final_sector = "Uncategorized"
                    stock = Stock(user_id=current_user.id, symbol=symbol, shares=item_data['shares'],
                                  purchase_price=item_data['price'], purchase_date=item_data['transaction_date'],
                                  sector=final_sector, custom_category=item_data['custom_category'] if item_data['custom_category'] else None)
                    db.session.add(stock)
                processed_transactions_count += 1

            elif op == 'sell_transaction':
                # For now, just logging it as processed. Actual share deduction would be here.
                stock = Stock.query.filter_by(user_id=current_user.id, symbol=symbol).first()
                if stock:
                    if stock.shares >= item_data['shares']:
                        stock.shares -= item_data['shares']
                        if stock.shares == 0: # Optional: delete stock if shares become zero
                            # db.session.delete(stock) 
                            pass # For now, keep it to show history, or implement a "closed position" status
                        processed_transactions_count += 1
                    else:
                        item_errors.append({'item_type': 'transaction', 'symbol': symbol, 'error': 'Attempted to sell more shares than owned.'})
                # If errors occur here after initial validation, they need to be handled for atomicity
        
        if item_errors: # Check for errors that might have occurred during processing sell transactions
            db.session.rollback()
            return jsonify({
                'error': 'Import processing error', 
                'details': 'Errors occurred during sell transaction processing. No data was imported.',
                'item_errors': item_errors,
            }), 422

        db.session.commit()
        return jsonify({
            'message': 'Generic JSON import processed successfully.',
            'processed_holdings': processed_holdings_count,
            'processed_transactions': processed_transactions_count,
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error during DB commit for generic JSON import: {e}")
        return jsonify({'error': 'Server Error', 'details': f'An unexpected error occurred during final import processing: {str(e)}'}), 500

from backend.services.financial_data import DEFAULT_BENCHMARK_SYMBOL, get_historical_data # Added for performance endpoint
from dateutil.relativedelta import relativedelta # For date calculations

# Portfolio Performance Endpoint
@portfolio_bp.route('/performance', methods=['GET'])
@subscription_required('allow_benchmarking')
def get_portfolio_performance(current_user):
    period = request.args.get('period', '1Y') # Default to 1 Year
    
    # 1. Determine Date Range
    end_date = datetime.utcnow().date()
    if period == '1M':
        start_date = end_date - relativedelta(months=1)
    elif period == '6M':
        start_date = end_date - relativedelta(months=6)
    elif period == '1Y':
        start_date = end_date - relativedelta(years=1)
    elif period == 'ALL':
        # For 'ALL', find the earliest purchase date of any stock in the portfolio
        earliest_stock_purchase = db.session.query(db.func.min(Stock.purchase_date))\
                                            .filter_by(user_id=current_user.id).scalar()
        if earliest_stock_purchase:
            start_date = earliest_stock_purchase.date()
            if start_date > end_date : start_date = end_date # Handle case where earliest purchase is in future (unlikely)
        else: # No stocks, so no performance data
            return jsonify({'message': 'No stocks in portfolio to calculate performance.'}), 200 
            
        # Cap 'ALL' period to a reasonable maximum to avoid excessive data, e.g., 5 years
        # This is important due to API limits and processing time.
        five_years_ago = end_date - relativedelta(years=5)
        if start_date < five_years_ago:
            start_date = five_years_ago
            print(f"Note: 'ALL' period capped at 5 years for performance calculation for user {current_user.id}")
    else:
        return jsonify({'error': 'Invalid period', 'details': 'Allowed periods: 1M, 6M, 1Y, ALL.'}), 400

    output_size = 'full' if (end_date - start_date).days > 100 else 'compact'


    # 2. Fetch User's Stocks
    user_stocks = Stock.query.filter_by(user_id=current_user.id).all()
    if not user_stocks:
        return jsonify({'message': 'No stocks in portfolio to calculate performance.'}), 200

    # 3. Fetch Benchmark Historical Data
    benchmark_history_raw = {}
    try:
        benchmark_data_list = get_historical_data(DEFAULT_BENCHMARK_SYMBOL, outputsize=output_size)
        if benchmark_data_list:
            for item in benchmark_data_list:
                # Filter by date range here as well, as API might return more than requested for 'compact'
                current_item_date = datetime.strptime(item['date'], '%Y-%m-%d').date()
                if start_date <= current_item_date <= end_date:
                    benchmark_history_raw[item['date']] = item['close'] # Using 'close' price
    except AlphaVantageError as e:
        print(f"Could not fetch benchmark data for {DEFAULT_BENCHMARK_SYMBOL}: {e}")
        # Proceed without benchmark if it fails, or return error
        # For now, proceed, frontend can handle missing benchmark_history
    except Exception as e:
        print(f"Unexpected error fetching benchmark data for {DEFAULT_BENCHMARK_SYMBOL}: {e}")


    # 4. Fetch Historical Data for Each User Stock (Optimized: fetch once per stock for the period)
    all_stocks_historical_data = {} # { 'SYMBOL': {'YYYY-MM-DD': close_price, ...}, ... }
    for stock in user_stocks:
        try:
            stock_history_list = get_historical_data(stock.symbol, outputsize=output_size)
            if stock_history_list:
                all_stocks_historical_data[stock.symbol] = {
                    item['date']: item['close'] for item in stock_history_list
                    if start_date <= datetime.strptime(item['date'], '%Y-%m-%d').date() <= end_date
                }
        except AlphaVantageError as e:
            print(f"Could not fetch historical data for user stock {stock.symbol}: {e}")
            # If a stock's history fails, it won't be included in daily portfolio value for days it's missing.
        except Exception as e:
            print(f"Unexpected error fetching historical data for user stock {stock.symbol}: {e}")


    # 5. Calculate Historical Portfolio Value & Align Data
    portfolio_history = []
    benchmark_history_aligned = []
    
    # Generate all dates in the range (daily)
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        daily_portfolio_value = 0.0
        
        for stock in user_stocks:
            # Stock must have been purchased on or before the current_date
            if stock.purchase_date.date() <= current_date:
                stock_symbol_history = all_stocks_historical_data.get(stock.symbol, {})
                price_on_that_day = stock_symbol_history.get(date_str)
                
                if price_on_that_day is not None:
                    daily_portfolio_value += stock.shares * price_on_that_day
                else:
                    # Carry forward last known value for this stock if price missing for a day?
                    # Simplification: if price missing, it contributes 0 for that day or we use last known value
                    # For now, if price is missing, it's not added. A more complex approach would find the *last available* price.
                    # This could lead to $0 portfolio value on some days if all stocks miss data.
                    pass 
        
        portfolio_history.append({"date": date_str, "value": round(daily_portfolio_value, 2)})
        
        # Align benchmark data
        benchmark_price_on_day = benchmark_history_raw.get(date_str)
        if benchmark_price_on_day is not None:
             benchmark_history_aligned.append({"date": date_str, "value": benchmark_price_on_day})
        # If benchmark data is missing for a day, we can omit it or carry forward.
        # For charting, it's often better to have corresponding points or handle gaps in frontend.
        # Here, we only add if available.

        current_date += relativedelta(days=1)
        
    # Note: AlphaVantage API limits (5 calls/min, 100-500/day) can be easily hit.
    # This endpoint is demanding. Caching in get_historical_data is crucial.
    # Warn user if data might be incomplete due to many stocks.
    if len(user_stocks) > 3 and ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER': # Rough check
        # Only show this specific warning if using placeholder key, as real key might have higher limits
         pass # This was too noisy, removed specific warning to client. Server logs are enough.
    elif len(user_stocks) > 10: # General caution for many stocks
        print(f"User {current_user.id} requested performance for {len(user_stocks)} stocks. API limits might be a concern.")


    return jsonify({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "benchmark_symbol": DEFAULT_BENCHMARK_SYMBOL,
        "portfolio_history": portfolio_history,
        "benchmark_history": benchmark_history_aligned
    }), 200
