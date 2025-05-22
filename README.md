# Stock Portfolio Tracker

## Description

The Stock Portfolio Tracker is a web application designed to help users manage their stock portfolios. It allows users to add stocks they own, track their current values based on real-time market data, view their portfolio's overall performance and allocation by sector, set price alerts, and stay updated with the latest financial news. The application also includes an admin dashboard for basic user and system monitoring.

## Features

*   **User Authentication:** Secure signup and login functionality using JWT for session management.
*   **Portfolio Management:**
    *   Add new stock holdings (symbol, shares, purchase price, purchase date, optional sector).
    *   View all stock holdings in a filterable and searchable table.
    *   Edit existing stock holdings.
    *   Delete stocks from the portfolio.
*   **Real-time Stock Price Updates:** Fetches current stock prices from Alpha Vantage when viewing the portfolio.
*   **Portfolio Value Calculation:** Displays the current market value for each stock and the total portfolio value. Calculates and displays total return.
*   **Sector Allocation Tracking & Charts:**
    *   Allows manual input of sector for a stock, or attempts to auto-fetch from Alpha Vantage.
    *   Displays portfolio allocation by sector using a doughnut chart (ECharts).
    *   Displays sector analysis using a pie chart (ECharts).
*   **Financial News Display:** Fetches and displays the latest general financial news from Alpha Vantage.
*   **Price Alert Management:**
    *   Create price alerts for specific stock symbols (e.g., when a price goes above or below a target).
    *   View active price alerts.
    *   Delete price alerts.
*   **CSV Data Import:** Allows users to bulk import stock transactions from a CSV file.
*   **Admin Dashboard:**
    *   Accessible by the admin user (user with ID=1).
    *   Displays user statistics (total users, users with portfolios, etc.).
    *   Shows system status (database and external API connectivity).
    *   Lists all registered users with basic details.
*   **Performance Chart:** Displays a line chart for the historical performance of the first stock in the user's portfolio (Chart.js).

## Technologies Used

*   **Frontend:**
    *   HTML5
    *   CSS3 (Inline styles within the HTML file)
    *   JavaScript (ES6+)
    *   Chart.js (for stock performance line chart)
    *   ECharts (for portfolio allocation and sector analysis pie charts)
    *   *Note: The original prompt mentioned Tailwind CSS and Alpine.js, but these were not used in the implementation. The styling is done via inline CSS within the HTML, and JavaScript is vanilla.*
*   **Backend:**
    *   Python 3
    *   Flask (Web framework)
    *   Flask-SQLAlchemy (ORM for database interaction)
    *   Werkzeug (for password hashing)
    *   PyJWT (for JSON Web Token generation and validation)
    *   Requests (for making HTTP requests to external APIs)
*   **Database:**
    *   SQLite (default for development, configured in `backend/app.py` as `portfolio.db`)
*   **APIs:**
    *   Alpha Vantage (for stock prices, historical data, company overview/sector, and financial news)

## Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   An Alpha Vantage API Key: Get one from [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)

## Setup Instructions

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
    (If you downloaded the files directly, navigate to the project's root directory).

2.  **Navigate to the Backend Directory:**
    ```bash
    cd backend
    ```

3.  **Create and Activate a Virtual Environment:**
    *   On macOS/Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```

4.  **Install Backend Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set Up Environment Variables:**
    Create a `.env` file in the `backend` directory or set the following environment variables directly in your shell. The Flask app in `backend/app.py` is configured to load these from a `.env` file if `python-dotenv` is installed (it's in `requirements.txt`).

    *   `ALPHA_VANTAGE_API_KEY`: Your actual Alpha Vantage API key.
        ```
        ALPHA_VANTAGE_API_KEY="YOUR_ALPHA_VANTAGE_KEY"
        ```
    *   `FLASK_APP`: The entry point for the Flask application. This is typically set in your shell.
        ```bash
        # For Linux/macOS
        export FLASK_APP=app.py
        # For Windows PowerShell
        $env:FLASK_APP="app.py"
        # For Windows CMD
        set FLASK_APP=app.py
        ```
    *   `SECRET_KEY`: A strong secret key for JWT and Flask session security. You can generate one using:
        ```bash
        python -c "import secrets; print(secrets.token_hex(24))" 
        ```
        Then add it to your `.env` file or set it as an environment variable:
        ```
        SECRET_KEY="your_generated_secret_key"
        ```
    *   `FLASK_ENV` (Optional, for development mode which enables debugging):
        ```
        FLASK_ENV=development
        ```

6.  **Initialize the Database:**
    The SQLite database file (`portfolio.db`) will be automatically created in the `backend` directory when the Flask application is first run. Flask-SQLAlchemy, as configured in `app.py` with the models, handles the creation of tables based on the defined models.

## Running the Application

1.  **Backend Server:**
    *   Ensure you are in the `backend` directory and your virtual environment is activated.
    *   Make sure the environment variables (`FLASK_APP`, `SECRET_KEY`, `ALPHA_VANTAGE_API_KEY`) are set.
    *   Run the Flask development server:
        ```bash
        flask run
        ```
        Alternatively, if `app.run(debug=True)` is enabled in `app.py` (which it is):
        ```bash
        python app.py
        ```
    *   The backend server will typically start on `http://127.0.0.1:5000/`.

2.  **Frontend Application:**
    *   Navigate to the project's root directory (the one containing `stock_portfolio_tracker.html`).
    *   Open the `stock_portfolio_tracker.html` file directly in your web browser (e.g., by double-clicking it or using "File > Open" in your browser).

## Project Structure

```
.
├── README.md
├── backend/
│   ├── app.py              # Main Flask application, configuration, routes registration
│   ├── requirements.txt    # Backend dependencies
│   ├── portfolio.db        # SQLite database file (created on first run)
│   ├── models/             # SQLAlchemy database models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── stock.py
│   │   └── alert.py
│   ├── routes/             # API route blueprints
│   │   ├── __init__.py
│   │   ├── auth.py         # Authentication routes (signup, login)
│   │   ├── portfolio.py    # Portfolio, stock, news, allocation routes
│   │   ├── alerts.py       # Price alert routes
│   │   └── admin.py        # Admin dashboard routes
│   └── services/           # Business logic for external services
│       ├── __init__.py
│       └── financial_data.py # Alpha Vantage API interaction
└── stock_portfolio_tracker.html # Main frontend HTML file (includes CSS and JavaScript)
```
*(Note: `backend/static` and `backend/templates` directories were initially created but are not extensively used as the frontend is a single HTML file and backend serves a JSON API.)*

## Admin User

*   The user with `ID = 1` is automatically considered an administrator.
*   To create an admin user:
    1.  Ensure the database (`backend/portfolio.db`) is fresh (delete it if it exists and you want to start over).
    2.  Sign up as the first user through the application's signup form. This user will be assigned ID 1.
    3.  Log in with this user's credentials. An "Admin" link will appear in the navigation bar, providing access to the Admin Dashboard modal.

## Notes & Considerations

*   **Production Deployment:**
    *   For a production environment, use a more robust database system (e.g., PostgreSQL, MySQL) instead of SQLite.
    *   Deploy the Flask backend using a production-ready WSGI server (e.g., Gunicorn, Waitress) behind a reverse proxy (e.g., Nginx).
    *   Ensure `FLASK_ENV` is set to `production` and `DEBUG` mode is `False` in the Flask app.
    *   Manage the `SECRET_KEY` securely, ideally not hardcoded or in version control for production.
*   **Alpha Vantage API Limits:** The free tier of Alpha Vantage has strict API call limits (e.g., 25 calls per day as of recent checks, previously higher). The application includes some basic caching for prices, company overviews, and news to mitigate this, but for heavy usage or more frequent updates, a premium API key would be necessary.
*   **Dividend History Chart:** The "Dividend History" chart on the dashboard is currently a placeholder with mock data, as dividend tracking functionality is not yet implemented in the backend.
*   **Error Handling:** While error handling is implemented for API routes and some frontend operations, more comprehensive logging (e.g., using Python's `logging` module on the backend) would be beneficial for a production application.
*   **Security:** The application implements several security practices (server-side validation, parameterized queries via SQLAlchemy, CSP meta tag, basic HTTP security headers, JWT authentication). A thorough security audit is recommended before production deployment.
*   **Background Tasks:** Features like checking price alerts and sending notifications would typically require a background task runner (e.g., Celery with Redis/RabbitMQ), which is not implemented in this version.
```
