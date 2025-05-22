import os
import requests
import time # For potential caching

# Attempt to get the API key from an environment variable
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER')
ALPHA_VANTAGE_BASE_URL = 'https://www.alphavantage.co/query'

# Simple in-memory cache to avoid hitting API rate limits too frequently
# { 'SYMBOL': (timestamp, price) }
PRICE_CACHE = {}
CACHE_DURATION_SECONDS = 300 # Cache price for 5 minutes

class AlphaVantageError(Exception):
    """Custom exception for Alpha Vantage API errors."""
    pass

def get_stock_price(symbol: str) -> float | None:
    """
    Fetches the current stock price for a given symbol from Alpha Vantage.
    Uses a simple in-memory cache to reduce API calls.
    """
    if not symbol:
        return None

    # Check cache first
    if symbol in PRICE_CACHE:
        timestamp, price = PRICE_CACHE[symbol]
        if time.time() - timestamp < CACHE_DURATION_SECONDS:
            print(f"Cache hit for {symbol}: {price}")
            return price
        else:
            print(f"Cache expired for {symbol}")
            del PRICE_CACHE[symbol] # Remove expired entry

    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print("WARN: Alpha Vantage API key is not set. Returning mock data or None for get_stock_price.")
        if symbol.upper() == "AAPL": return {"price": 150.0, "sector": "Technology"}
        if symbol.upper() == "MSFT": return {"price": 300.0, "sector": "Technology"}
        if symbol.upper() == "JNJ": return {"price": 160.0, "sector": "Healthcare"}
        return {"price": None, "sector": None}


    # First, try to get company overview for sector (less frequent call, cache it)
    # This is a simplified approach; ideally, overview and quote are separate and cached independently.
    overview_data = get_company_overview(symbol) # New function to be defined
    sector = overview_data.get('sector') if overview_data else None

    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': ALPHA_VANTAGE_API_KEY
    }
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=10) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()

        if "Global Quote" not in data or not data["Global Quote"]:
            # This can happen for invalid symbols or if the API returns an empty quote
            print(f"Warning: 'Global Quote' not found or empty for symbol {symbol}. Response: {data}")
            if "Note" in data : # API limit often comes with a "Note"
                 raise AlphaVantageError(f"API Error for {symbol}: {data.get('Note')}")
            if "Error Message" in data: # Specific error from API
                 raise AlphaVantageError(f"API Error for {symbol}: {data.get('Error Message')}")
            return None
        
        price_str = data["Global Quote"].get("05. price")
        if price_str is None:
            print(f"Warning: '05. price' not found for symbol {symbol}. Response: {data}")
            return None

        price = float(price_str)
        
        # Update cache for price (overview is cached in its own function)
        PRICE_CACHE[symbol] = (time.time(), price) # Note: Caching only price here. Sector comes from get_company_overview
        print(f"Cache miss for {symbol} price: fetched {price}")
        return {"price": price, "sector": sector} # Return price and sector

    except requests.exceptions.Timeout:
        print(f"Error fetching price for {symbol}: Request timed out.")
        raise AlphaVantageError(f"Request timed out for {symbol}")
    except requests.exceptions.HTTPError as http_err:
        print(f"Error fetching price for {symbol}: HTTP error occurred: {http_err} - {response.text}")
        raise AlphaVantageError(f"HTTP error for {symbol}: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Error fetching price for {symbol}: Request exception: {req_err}")
        raise AlphaVantageError(f"Request failed for {symbol}: {req_err}")
    except ValueError: # For float conversion error
        print(f"Error fetching price for {symbol}: Could not convert price to float. Data: {data}")
        raise AlphaVantageError(f"Data parsing error for {symbol}")
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred while fetching price for {symbol}: {e}")
        raise AlphaVantageError(f"Unexpected error for {symbol}: {e}")

# Cache for Company Overview (Sector Info)
OVERVIEW_CACHE = {} # { 'SYMBOL': (timestamp, overview_data) }
OVERVIEW_CACHE_DURATION_SECONDS = 86400 # Cache overview data for 24 hours (sector changes infrequently)

def get_company_overview(symbol: str) -> dict | None:
    """
    Fetches company overview data (including sector) for a given symbol from Alpha Vantage.
    Uses a simple in-memory cache.
    """
    if not symbol:
        return None

    symbol_upper = symbol.upper()
    if symbol_upper in OVERVIEW_CACHE:
        timestamp, data = OVERVIEW_CACHE[symbol_upper]
        if time.time() - timestamp < OVERVIEW_CACHE_DURATION_SECONDS:
            print(f"Overview cache hit for {symbol_upper}")
            return data
        else:
            print(f"Overview cache expired for {symbol_upper}")
            del OVERVIEW_CACHE[symbol_upper]

    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print(f"WARN: Alpha Vantage API key is not set. Returning mock overview for {symbol_upper}.")
        if symbol_upper == "AAPL": return {"Sector": "Technology", "Name": "Apple Inc."}
        if symbol_upper == "MSFT": return {"Sector": "Technology", "Name": "Microsoft Corp."}
        if symbol_upper == "JNJ": return {"Sector": "Healthcare", "Name": "Johnson & Johnson"}
        return {"Sector": "Unknown", "Name": "Unknown Company"}


    params = {
        'function': 'OVERVIEW',
        'symbol': symbol_upper,
        'apikey': ALPHA_VANTAGE_API_KEY
    }
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or "Symbol" not in data or data["Symbol"] != symbol_upper :
             # If data is empty or doesn't match the symbol, or is just a note about API calls
            if data.get("Note") or data.get("Information"):
                raise AlphaVantageError(f"API Note for {symbol_upper} overview: {data.get('Note') or data.get('Information')}")
            print(f"Warning: Company overview not found or invalid for symbol {symbol_upper}. Response: {data}")
            return None
        
        overview_data = {
            "symbol": data.get("Symbol"),
            "name": data.get("Name"),
            "sector": data.get("Sector"),
            "industry": data.get("Industry")
            # Add other fields from overview if needed
        }
        
        OVERVIEW_CACHE[symbol_upper] = (time.time(), overview_data)
        print(f"Overview cache miss for {symbol_upper}: fetched.")
        return overview_data

    except requests.exceptions.Timeout:
        print(f"Error fetching overview for {symbol_upper}: Request timed out.")
        raise AlphaVantageError(f"Request timed out for {symbol_upper} overview.")
    except requests.exceptions.HTTPError as http_err:
        print(f"Error fetching overview for {symbol_upper}: HTTP error: {http_err} - {response.text}")
        raise AlphaVantageError(f"HTTP error for {symbol_upper} overview: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Error fetching overview for {symbol_upper}: Request exception: {req_err}")
        raise AlphaVantageError(f"Request failed for {symbol_upper} overview: {req_err}")
    except ValueError: # For JSON decoding error
        print(f"Error fetching overview for {symbol_upper}: Could not decode JSON response.")
        raise AlphaVantageError(f"Data parsing error for {symbol_upper} overview.")
    except Exception as e:
        print(f"An unexpected error occurred while fetching overview for {symbol_upper}: {e}")
        raise AlphaVantageError(f"Unexpected error for {symbol_upper} overview: {e}")

# Cache for Historical Data
HISTORICAL_DATA_CACHE = {} # { 'SYMBOL_outputsize': (timestamp, data) }
# Shorter cache for general stocks, longer for benchmarks
GENERAL_HISTORICAL_CACHE_DURATION_SECONDS = 3600 # 1 hour for general stocks
BENCHMARK_HISTORICAL_CACHE_DURATION_SECONDS = 14400 # 4 hours for benchmarks (e.g. SPY)
BENCHMARK_SYMBOLS = ['SPY', 'QQQ', 'DIA'] # Define common benchmark symbols

DEFAULT_BENCHMARK_SYMBOL = 'SPY' # Can be made configurable later


def get_historical_data(symbol: str, outputsize: str = 'compact') -> list | None:
    """
    Fetches daily time series (historical data) for a given symbol from Alpha Vantage.
    Uses a specific cache for historical data with longer duration for benchmark symbols.
    `outputsize` can be 'compact' (last 100 data points) or 'full' (full history).
    """
    if not symbol:
        return None

    symbol_upper = symbol.upper()
    cache_key = f"{symbol_upper}_{outputsize}"
    
    is_benchmark = symbol_upper in BENCHMARK_SYMBOLS
    cache_duration = BENCHMARK_HISTORICAL_CACHE_DURATION_SECONDS if is_benchmark else GENERAL_HISTORICAL_CACHE_DURATION_SECONDS

    if cache_key in HISTORICAL_DATA_CACHE:
        timestamp, data = HISTORICAL_DATA_CACHE[cache_key]
        if time.time() - timestamp < cache_duration:
            print(f"Historical data cache hit for {cache_key} (Benchmark: {is_benchmark})")
            return data
        else:
            print(f"Historical data cache expired for {cache_key}")
            del HISTORICAL_DATA_CACHE[cache_key]


    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print(f"WARN: Alpha Vantage API key is not set. Returning mock historical data for {symbol_upper}.")
        mock_data_point_count = 100 if outputsize == 'compact' else 200 # Simulate outputsize
        mock_data = []
        for i in range(mock_data_point_count):
            # Create somewhat realistic date strings, going backwards
            day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Vary price slightly based on symbol for more diverse mock data
            base_price = 150.0
            if symbol_upper == "MSFT": base_price = 300.0
            elif symbol_upper == "SPY": base_price = 400.0
            
            mock_data.append({
                "date": day, 
                "open": base_price + i*0.1,
                "high": base_price + i*0.1 + 2,
                "low": base_price + i*0.1 - 2,
                "close": base_price + i*0.1 + 1, # Mock price
                "adjusted_close": base_price + i*0.1 + 1,
                "volume": 1000000 + i*1000
            })
        return sorted(mock_data, key=lambda x: x['date']) if mock_data else None


    params = {
        'function': 'TIME_SERIES_DAILY_ADJUSTED', 
        'symbol': symbol_upper,
        'apikey': ALPHA_VANTAGE_API_KEY,
        'outputsize': outputsize 
    }
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=15) 
        response.raise_for_status()
        api_data = response.json() # Renamed to api_data to avoid conflict with cached 'data'

        if "Time Series (Daily)" not in api_data:
            note = api_data.get("Information") or api_data.get("Note")
            if note and "higher subscription" in note.lower(): # Check for API plan limits
                 raise AlphaVantageError(f"API Note for {symbol_upper} historical data: {note}. Your current Alpha Vantage plan may not support this query or outputsize.")
            print(f"Warning: 'Time Series (Daily)' not found for symbol {symbol_upper}. Response: {api_data}")
            if "Error Message" in api_data: # Specific error from API
                 raise AlphaVantageError(f"API Error for historical data {symbol_upper}: {api_data.get('Error Message')}")
            return None # Return None if data is not in expected format

        time_series = api_data["Time Series (Daily)"]
        parsed_data = []
        for date_str, daily_values in time_series.items():
            try:
                parsed_data.append({
                    "date": date_str,
                    "open": float(daily_values.get("1. open", 0)), # Use .get for safety
                    "high": float(daily_values.get("2. high", 0)),
                    "low": float(daily_values.get("3. low", 0)),
                    "close": float(daily_values.get("4. close", 0)),
                    "adjusted_close": float(daily_values.get("5. adjusted close", 0)),
                    "volume": int(daily_values.get("6. volume", 0))
                })
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse daily data for {symbol_upper} on {date_str}. Error: {e}. Data: {daily_values}")
                continue # Skip this data point if parsing fails for a day
        
        if not parsed_data: # If all points failed parsing
            print(f"Warning: No valid historical data points could be parsed for {symbol_upper}.")
            return None

        # Sort by date ascending (Alpha Vantage usually returns descending)
        parsed_data.sort(key=lambda x: x['date'])
        
        HISTORICAL_DATA_CACHE[cache_key] = (time.time(), parsed_data)
        print(f"Historical data cache miss for {cache_key} (Benchmark: {is_benchmark})")
        return parsed_data

    except requests.exceptions.Timeout:
        print(f"Error fetching historical data for {symbol_upper}: Request timed out.")
        raise AlphaVantageError(f"Request timed out for historical data of {symbol_upper}")
    except requests.exceptions.HTTPError as http_err:
        print(f"Error fetching historical data for {symbol_upper}: HTTP error: {http_err} - {response.text}")
        raise AlphaVantageError(f"HTTP error for historical data of {symbol_upper}: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Error fetching historical data for {symbol_upper}: Request exception: {req_err}")
        raise AlphaVantageError(f"Request failed for historical data of {symbol_upper}: {req_err}")
    except ValueError: # For JSON decoding error or float/int conversion errors not caught above
        print(f"Error fetching/parsing historical data for {symbol_upper}: Could not parse data. API Response: {api_data if 'api_data' in locals() else 'N/A'}")
        raise AlphaVantageError(f"Data parsing error for historical data of {symbol_upper}")
    except Exception as e:
        print(f"An unexpected error occurred while fetching historical data for {symbol_upper}: {e}")
        raise AlphaVantageError(f"Unexpected error for historical data of {symbol_upper}: {e}")


from datetime import timedelta # Add timedelta for mock data generation

if __name__ == '__main__':
    # Example usage (for testing this file directly)
    # Make sure to set your ALPHA_VANTAGE_API_KEY environment variable
    # export ALPHA_VANTAGE_API_KEY="YOURKEY"
    
    # Test with placeholder key
    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print("Testing with placeholder API Key...")
        # Test get_stock_price (which now includes sector from mock get_company_overview)
        for s in ["AAPL", "MSFT", "JNJ", "UNKNOWN"]:
            data = get_stock_price(s)
            print(f"Mock Data for {s}: Price=${data.get('price')}, Sector='{data.get('sector')}'")

        print(f"Mock Historical for AAPL: {get_historical_data('AAPL')}")
    else:
        print("Testing with actual API Key (ensure it's set in your environment)...")
        symbols_to_test = ["AAPL", "MSFT", "GOOGL", "INVALID"] # Keep INVALID to test error handling
        for symbol in symbols_to_test:
            try:
                # Test overview
                overview = get_company_overview(symbol)
                if overview and overview.get('sector'):
                    print(f"Overview for {symbol}: Name='{overview.get('name')}', Sector='{overview.get('sector')}'")
                else:
                    print(f"Could not retrieve overview or sector for {symbol}.")
                
                time.sleep(13) # Be very mindful of API limits with multiple calls per symbol

                # Test price (which internally calls overview again, but should hit cache)
                price_data = get_stock_price(symbol)
                if price_data and price_data.get('price') is not None:
                    print(f"Current price for {symbol}: ${price_data['price']:.2f}, Sector from price_data: '{price_data.get('sector')}'")
                else:
                    print(f"Could not retrieve price for {symbol}.")
                
                time.sleep(13) # Respect API limits

                # Test historical data
                history = get_historical_data(symbol)
                if history:
                    print(f"Historical data for {symbol} (first 2 entries): {history[:2]}")
                else:
                    print(f"Could not retrieve historical data for {symbol}.")

            except AlphaVantageError as e:
                print(f"AlphaVantage API Error for {symbol}: {e}")
            except Exception as e:
                print(f"General error during test for {symbol}: {e}")
            time.sleep(13) # Alpha Vantage free tier is 5 calls/min, so be respectful
            
    # Test caching
    if ALPHA_VANTAGE_API_KEY != 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print("\nTesting caching for AAPL (should hit API first, then cache for both overview and price):")
        try:
            get_company_overview("AAPL") # Prime overview cache
            time.sleep(13)
            get_stock_price("AAPL")      # Prime price cache, uses cached overview
            time.sleep(1)
            get_company_overview("AAPL") # Should hit cache
            get_stock_price("AAPL")      # Should hit price cache and use cached overview
        except AlphaVantageError as e:
            print(f"Error during caching test: {e}")
        except Exception as e:
            print(f"General error during caching test: {e}")

# News Cache
NEWS_CACHE = {} # { 'topics_key': (timestamp, news_data) }
NEWS_CACHE_DURATION_SECONDS = 1800 # Cache news for 30 minutes

def get_latest_financial_news(topics=None, tickers=None, limit=20) -> list | None:
    """
    Fetches latest financial news from Alpha Vantage.
    Can filter by topics (e.g., ['technology', 'earnings']) OR by tickers.
    Alpha Vantage 'NEWS_SENTIMENT' endpoint is used.
    If both topics and tickers are None, it will attempt to fetch general financial news.
    """
    cache_key_parts = []
    if topics:
        cache_key_parts.extend(sorted([t.lower() for t in topics]))
    if tickers:
        cache_key_parts.extend(sorted([t.lower() for t in tickers]))
    if not cache_key_parts:
        cache_key_parts.append("general_financial_news") # Default key if no specifics
    
    cache_key = "_".join(cache_key_parts) + f"_limit{limit}"

    if cache_key in NEWS_CACHE:
        timestamp, cached_news = NEWS_CACHE[cache_key]
        if time.time() - timestamp < NEWS_CACHE_DURATION_SECONDS:
            print(f"News cache hit for key: {cache_key}")
            return cached_news
        else:
            print(f"News cache expired for key: {cache_key}")
            del NEWS_CACHE[cache_key]

    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print("WARN: Alpha Vantage API key is not set for news. Returning mock news.")
        # Return more generic mock news
        return [
            {"title": "Market Hits Record Highs Amidst Tech Rally", "source": "Mock News Service", "url": "#", "summary": "Major indices surged today, driven by strong earnings in the tech sector and positive economic outlook.", "published_at": "2024-03-15T10:00:00Z", "banner_image": "https://via.placeholder.com/150/007bff/FFFFFF?Text=Market+High"},
            {"title": "Federal Reserve Signals Steady Interest Rates", "source": "Financial Times Mock", "url": "#", "summary": "The Federal Reserve concluded its policy meeting today, indicating that interest rates will likely remain unchanged for the near future.", "published_at": "2024-03-15T09:30:00Z", "banner_image": "https://via.placeholder.com/150/28a745/FFFFFF?Text=Fed+Rates"},
            {"title": "Global Supply Chain Challenges Easing, Report Suggests", "source": "Reuters Mock", "url": "#", "summary": "A new report indicates that global supply chain pressures are beginning to ease, which could help reduce inflation.", "published_at": "2024-03-15T08:00:00Z", "banner_image": "https://via.placeholder.com/150/ffc107/000000?Text=Supply+Chain"}
        ] * (limit // 3) # Repeat mock news to somewhat respect limit

    params = {
        'function': 'NEWS_SENTIMENT',
        'apikey': ALPHA_VANTAGE_API_KEY,
        'limit': limit, # Alpha Vantage limit is up to 1000, but free tier might be less. Defaulting to a small number.
        'sort': 'LATEST' # Fetch latest news
    }

    # Alpha Vantage API prefers either tickers or topics, not both in the same query for best results.
    # If topics are provided, use them. Otherwise, if tickers are provided, use them.
    # If neither, it fetches general news.
    if topics and isinstance(topics, list):
        params['topics'] = ",".join(topics).upper() # E.g., "TECHNOLOGY,EARNINGS"
    elif tickers and isinstance(tickers, list):
        params['tickers'] = ",".join(tickers).upper() # E.g., "AAPL,MSFT"
    else:
        # For more general news, we can try a broad topic like 'ECONOMY' or 'FINANCE'
        # or specific broad market ETFs if general topic isn't good.
        # Let's default to a mix of common topics if none are specified for "general" news.
        params['topics'] = "FINANCE,ECONOMY,TECHNOLOGY"


    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if "feed" not in data or not data["feed"]:
            note = data.get("Information") or data.get("Note")
            if note and "higher subscription" in note.lower():
                 raise AlphaVantageError(f"API Note: {note}. Your current Alpha Vantage plan may not support this news query.")
            print(f"Warning: 'feed' not found or empty in news response. Params: {params} Response: {data}")
            return [] # Return empty list if no news items

        news_items = []
        for item in data["feed"]:
            news_items.append({
                "title": item.get("title", "No Title"),
                "source": item.get("source", "Unknown Source"),
                "url": item.get("url", "#"),
                "summary": item.get("summary", "No summary available."),
                "published_at": item.get("time_published", ""), # Format: YYYYMMDDTHHMMSS
                "banner_image": item.get("banner_image", "https://via.placeholder.com/100x60/eee/999?text=News") # Placeholder if no image
                # Add other relevant fields if needed, e.g., sentiment data if available
            })
        
        NEWS_CACHE[cache_key] = (time.time(), news_items)
        return news_items

    except requests.exceptions.Timeout:
        print(f"Error fetching news: Request timed out. Params: {params}")
        raise AlphaVantageError("Request timed out while fetching news.")
    except requests.exceptions.HTTPError as http_err:
        print(f"Error fetching news: HTTP error occurred: {http_err} - {response.text}. Params: {params}")
        raise AlphaVantageError(f"HTTP error while fetching news: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Error fetching news: Request exception: {req_err}. Params: {params}")
        raise AlphaVantageError(f"Request failed while fetching news: {req_err}")
    except ValueError: # For JSON decoding error
        print(f"Error fetching news: Could not decode JSON response. Params: {params}")
        raise AlphaVantageError("Failed to parse news data.")
    except Exception as e:
        print(f"An unexpected error occurred while fetching news: {e}. Params: {params}")
        raise AlphaVantageError(f"An unexpected error occurred fetching news: {e}")

if __name__ == '__main__':
    # ... (existing test code for get_stock_price and get_historical_data) ...

    print("\n--- Testing News Fetching ---")
    if ALPHA_VANTAGE_API_KEY == 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER':
        print("Testing news with placeholder API Key (mock data)...")
        mock_news = get_latest_financial_news(limit=5)
        if mock_news:
            for article in mock_news:
                print(f"- {article['title']} ({article['source']})")
        else:
            print("No mock news returned.")
    else:
        print("Testing news with actual API Key (ensure it's set)...")
        try:
            # Test general news
            print("\nFetching general news (topics: FINANCE, ECONOMY, TECHNOLOGY)...")
            general_news = get_latest_financial_news(limit=3)
            if general_news:
                for article in general_news:
                    print(f"- {article['title']} ({article['source']}) URL: {article['url']}")
            else:
                print("No general news returned or error occurred.")
            time.sleep(15) # Respect API limits

            # Test news by specific topics
            print("\nFetching news for topic: TECHNOLOGY...")
            tech_news = get_latest_financial_news(topics=['technology'], limit=2)
            if tech_news:
                for article in tech_news:
                    print(f"- {article['title']} ({article['source']})")
            else:
                print("No technology news returned or error occurred.")
            time.sleep(15)

            # Test news by specific tickers
            print("\nFetching news for tickers: AAPL, TSLA...")
            ticker_news = get_latest_financial_news(tickers=['AAPL', 'TSLA'], limit=2) # limit here is total, not per ticker by AV API
            if ticker_news:
                for article in ticker_news:
                    print(f"- {article['title']} ({article['source']})")
            else:
                print("No ticker-specific news returned or error occurred.")
            
            # Test caching
            print("\nTesting news caching (should hit API first, then cache for general news):")
            get_latest_financial_news(limit=3) # First call
            time.sleep(1)
            get_latest_financial_news(limit=3) # Second call - should be cached

        except AlphaVantageError as e:
            print(f"AlphaVantage API Error during news test: {e}")
        except Exception as e:
            print(f"General error during news test: {e}")
```python
# This is a placeholder for where backend/app.py or a config file would
# typically load and make the API key available to the application.
# For now, backend/services/financial_data.py directly uses os.getenv().

# Example of how it might be integrated into app.py:
# from flask import Flask
# import os

# app = Flask(__name__)
# app.config['ALPHA_VANTAGE_API_KEY'] = os.getenv('ALPHA_VANTAGE_API_KEY', 'YOUR_ALPHA_VANTAGE_API_KEY_PLACEHOLDER')

# Then in services/financial_data.py, you might import and use app.config:
# from backend.app import app # Assuming app is importable
# ALPHA_VANTAGE_API_KEY = app.config.get('ALPHA_VANTAGE_API_KEY')
```
