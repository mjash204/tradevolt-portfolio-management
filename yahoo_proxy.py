from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests
from datetime import datetime, timedelta
import json

app = Flask(__name__)
CORS(app)  # This enables CORS for all routes

# Cache to store recent data and avoid too many API calls
cache = {}
CACHE_DURATION = 60  # Cache for 60 seconds

def is_cache_valid(timestamp):
    """Check if cached data is still valid"""
    return datetime.now() - timestamp < timedelta(seconds=CACHE_DURATION)

@app.route('/api/yahoo-finance/<symbol>')
def get_yahoo_data(symbol):
    """
    Get real-time stock data for a given symbol
    Example: /api/yahoo-finance/RELIANCE.NS
    """
    try:
        # Check cache first
        if symbol in cache and is_cache_valid(cache[symbol]['timestamp']):
            print(f"Returning cached data for {symbol}")
            return jsonify(cache[symbol]['data'])
        
        print(f"Fetching fresh data for {symbol}")
        
        # Create ticker object
        ticker = yf.Ticker(symbol)
        
        # Get current info
        info = ticker.info
        
        # Get recent history (last 2 days to ensure we have data)
        hist = ticker.history(period="2d", interval="1d")
        
        if hist.empty:
            return jsonify({'error': f'No data available for symbol {symbol}'}), 404
        
        # Get the most recent data
        current_price = float(hist['Close'].iloc[-1])
        
        # Get previous close (try from info first, then from history)
        previous_close = info.get('previousClose')
        if previous_close is None and len(hist) > 1:
            previous_close = float(hist['Close'].iloc[-2])
        elif previous_close is None:
            previous_close = current_price
        else:
            previous_close = float(previous_close)
        
        # Calculate change
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
        
        # Prepare response in Yahoo Finance API format
        response_data = {
            'chart': {
                'result': [{
                    'meta': {
                        'currency': info.get('currency', 'INR'),
                        'symbol': symbol,
                        'regularMarketPrice': current_price,
                        'previousClose': previous_close,
                        'regularMarketChange': change,
                        'regularMarketChangePercent': change_percent / 100,
                        'regularMarketTime': int(datetime.now().timestamp()),
                        'shortName': info.get('shortName', symbol),
                        'longName': info.get('longName', symbol)
                    }
                }],
                'error': None
            }
        }
        
        # Cache the response
        cache[symbol] = {
            'data': response_data,
            'timestamp': datetime.now()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Error fetching data for {symbol}: {str(e)}"
        print(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/yahoo-finance/bulk')
def get_bulk_yahoo_data():
    """
    Get data for multiple symbols at once
    Usage: /api/yahoo-finance/bulk?symbols=RELIANCE.NS,TCS.NS,INFY.NS
    """
    try:
        symbols_param = request.args.get('symbols', '')
        if not symbols_param:
            return jsonify({'error': 'No symbols provided'}), 400
        
        symbols = [s.strip() for s in symbols_param.split(',')]
        results = {}
        
        for symbol in symbols:
            try:
                # Check cache first
                if symbol in cache and is_cache_valid(cache[symbol]['timestamp']):
                    results[symbol] = cache[symbol]['data']
                    continue
                
                # Fetch fresh data
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period="2d", interval="1d")
                
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    previous_close = info.get('previousClose', current_price)
                    if previous_close != current_price and len(hist) > 1:
                        previous_close = float(hist['Close'].iloc[-2])
                    else:
                        previous_close = float(previous_close) if previous_close else current_price
                    
                    change = current_price - previous_close
                    change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
                    
                    response_data = {
                        'chart': {
                            'result': [{
                                'meta': {
                                    'symbol': symbol,
                                    'regularMarketPrice': current_price,
                                    'previousClose': previous_close,
                                    'regularMarketChange': change,
                                    'regularMarketChangePercent': change_percent / 100,
                                    'shortName': info.get('shortName', symbol)
                                }
                            }]
                        }
                    }
                    
                    # Cache the data
                    cache[symbol] = {
                        'data': response_data,
                        'timestamp': datetime.now()
                    }
                    
                    results[symbol] = response_data
                else:
                    results[symbol] = {'error': f'No data for {symbol}'}
                    
            except Exception as e:
                results[symbol] = {'error': str(e)}
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/nifty-data')
def get_nifty_data():
    """Get NIFTY 50 index data"""
    return get_yahoo_data('^NSEI')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(cache)
    })

if __name__ == '__main__':
    print("Starting Yahoo Finance Proxy Server...")
    print("Available endpoints:")
    print("- http://localhost:5000/api/yahoo-finance/<symbol>")
    print("- http://localhost:5000/api/yahoo-finance/bulk?symbols=SYM1,SYM2")
    print("- http://localhost:5000/api/nifty-data")
    print("- http://localhost:5000/health")
    
    app.run(host='0.0.0.0', port=5000, debug=True)