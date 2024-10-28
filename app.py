import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]

    # Fetch user's cash balance
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # Fetch user's stock holdings
    holdings = db.execute("""
                          SELECT symbol, SUM(shares) AS total_shares
                          FROM transactions
                          WHERE user_id = ?
                          GROUP BY symbol
                          HAVING total_shares > 0
                          """, user_id)

    # Initialize the grand_total as the current cash balance
    grand_total = cash

    # Initialize a list to hold portfolio details
    portfolio = []

    # Loop through each holding to get the current price and total value
    for holding in holdings:
        symbol = holding["symbol"]
        shares = holding["total_shares"]

        # Look up the current price of the stock
        stock = lookup(symbol)

        if stock:
            current_price = stock["price"]
            total_value = shares * current_price

            # Add to grand_total
            grand_total += total_value

            # Add info to portfolio
            portfolio.append({
                "symbol": symbol,
                "shares": shares,
                "current_price": current_price,
                "total_value": total_value
            })

    return render_template("index.html", portfolio=portfolio, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure symbol was submitted
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        # Ensure symbol exists
        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol", 400)

        # Ensure shares were submitted
        shares = request.form.get("shares")
        if not shares:
            return apology("missing shares", 400)

        # Ensure shares is a positive integer
        try:
            shares = int(shares)
            if shares <= 0:
                return apology("invalid number of shares", 400)
        except ValueError:
            return apology("invalid number of shares", 400)

        # Look up the stock's current price
        price = stock["price"]

        # Look up how much cash the user currently has
        user_id = session["user_id"]

        # Execute the query to obtain the cash value
        result = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        if len(result) != 1:
            return apology("user not found", 404)

        # Get the cash value from the result
        cash = result[0]["cash"]

        # Get the cost of the specified number of shares selected
        purchase_price = shares * price

        # Check if user can afford the stocks
        if purchase_price > cash:
            return apology("can't afford", 400)

        # Update user's cash balance
        updated_cash = cash - purchase_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)

        # Insert transaction into transactions table
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
            user_id, symbol.upper(), shares, price
        )

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    # Fetch all transactions for the user
    transactions = db.execute("""
                              SELECT symbol, shares, price, timestamp
                              FROM transactions
                              WHERE user_id = ?
                              ORDER BY timestamp
                              """, user_id)

    # Render history template
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST"
    if request.method == "POST":
        # Obtain price and symbol of stock
        stock_quote = lookup(request.form.get("symbol"))

        # Check if lookup is unsuccessful
        if not stock_quote:
            return apology("invalid symbol", 400)

        # Pass values into template
        return render_template("quoted.html", stock_quote=stock_quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST
    if request.method == "POST":
        # Ensure username was submitted
        username = request.form.get("username")
        if not username:
            return apology("missing username", 400)

        # Ensure password was submitted
        password = request.form.get("password")
        if not password:
            return apology("missing password", 400)

        # Ensure confirmation was submitted
        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("passwords don't match", 400)

        # Ensure password and confirmation match
        if password != confirmation:
            return apology("passwords don't match", 400)

        try:
            # Generate password hash
            password_hash = generate_password_hash(password)

            # Insert new user into database
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password_hash)

        except ValueError:
            # Catches UNIQUE constraint failure
            return apology("username already exists", 400)

        # Query database for new user's id
        user = db.execute("SELECT id FROM users WHERE username = ?", username)
        if len(user) != 1:
            return apology("registration failed", 400)

        # Log user in
        session["user_id"] = user[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    # User reached route via POST
    if request.method == "POST":
        # Get form data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Ensure symbol submitted
        if not symbol:
            return apology("missing symbol", 400)

        # Ensure shares submitted
        if not shares:
            return apology("missing shares", 400)

        # Ensure shares is a positive integer
        try:
            shares = int(shares)
            if shares <= 0:
                return apology("shares must be positive", 400)
        except ValueError:
            return apology("shares must be an integer", 400)

        # Check if user owns the stock and has enough to sell
        rows = db.execute("SELECT SUM(shares) AS total_shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol",
                          user_id, symbol)
        if len(rows) != 1 or rows[0]["total_shares"] < shares:
            return apology("too many shares", 400)

        # Get current stock price
        stock = lookup(symbol)
        if not stock:
            return apology("invalid stock symbol", 400)
        price = stock["price"]

        # Get total value of sale
        sale_value = shares * price

        # Update cash balance of user
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sale_value, user_id)

        # Record sale
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
            user_id, symbol, -shares, price
        )

        # Redirect to home page
        return redirect("/")

    else:
        # Get user's stocks
        stocks = db.execute(
            "SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
            user_id
        )
        return render_template("sell.html", stocks=stocks)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        # Ensure old password was submitted
        old_password = request.form.get("old_password")
        if not old_password:
            return apology("must provide old password", 403)

        # Ensure new password was submitted
        new_password = request.form.get("new_password")
        if not new_password:
            return apology("must provide new password", 403)

        # Ensure confirmation was submitted
        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("must provide confirmation", 403)

        # Query database for the user
        user_id = session["user_id"]
        rows = db.execute("SELECT * FROM users WHERE id = ?", user_id)

        # Ensure old password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], old_password):
            return apology("invalid old password", 403)

        # Ensure new password and confirmation match
        if new_password != confirmation:
            return apology("confirmation does not match the new password", 403)

        # Update password
        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_hash, user_id)

        # Flash success message
        flash("Password successfully changed")

        # Return to homepage
        return redirect("/")

    else:
        return render_template("change_password.html")
