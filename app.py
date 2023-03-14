import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# export API_KEY=pk_4eaf5a3722b14f83a9e04aba16191342

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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

    stocks = db.execute("SELECT symbol, name, price, SUM(shares) as totalShares FROM transactions WHERE user_id = ? GROUP BY symbol ORDER BY name", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    total = cash

    for stock in stocks:
        stock["price"] = lookup(stock["symbol"])["price"]
        total += stock["price"] * stock["totalShares"]

    return render_template("index.html", stocks=stocks, cash=cash, usd=usd, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        item = lookup(symbol)

        if not symbol:
            return apology("must enter symbol")
        elif not item:
            return apology("invalid symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a number")

        if shares <= 0:
            return apology("shares must be a positive number")

        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        item_name = item["name"]
        item_price = item["price"]
        total_price = item_price * shares

        if total_price > user_cash:
            return apology("not enough cash", 403)
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash - total_price, user_id)
            db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES(?, ?, ?, ?, ?, ?)",
                       user_id, item_name, shares, item_price, "buy", item["symbol"])
        flash("Bought!")
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_id = session["user_id"]
    transactions = db.execute("SELECT symbol, price, shares, time FROM transactions WHERE user_id = ? ORDER BY time DESC", user_id)

    return render_template("history.html", transactions=transactions, usd=usd)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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

    if request.method == "POST":

        symbol = request.form.get("symbol")
        item = lookup(symbol)

        if not symbol:
            return apology("must enter symbol")
        elif not item:
            return apology("invalid symbol")

        return render_template("quoted.html", symbol=item, usd=usd)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username")
        elif not password:
            return apology("must provide password")
        elif not confirmation:
            return apology("must provide confirmation")

        if password != confirmation:
            return apology("confirmation does not match")

        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))
            return redirect("/")
        except:
            return apology("username already exists")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        name = lookup(symbol)["name"]
        price = lookup(symbol)["price"]
        total_price = shares * price

        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        user_shares = db.execute("SELECT shares FROM transactions WHERE symbol = ? AND user_id = ? GROUP BY symbol", symbol, user_id)[0]["shares"]

        if not symbol:
            return apology("must enter symbol")
        elif not shares:
            return apology("must enter symbol")

        if shares <= 0:
            return apology("shares must be a positive number")
        elif shares > user_shares:
            return apology("more shares than owned")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + total_price, user_id)
        db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES(?, ?, ?, ?, ?, ?)",
                   user_id, name, -shares, price, "sell", symbol)
        flash("Sold!")
        return redirect("/")

    else:
        options = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol ORDER BY symbol", user_id)
        return render_template("sell.html", options=options)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """allow users to deposit"""
    user_id = session["user_id"]
    if request.method == "POST":
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        amount = int(request.form.get("amount"))

        if not amount:
            return apology("must enter amount")
        if amount <= 0:
            return apology("amount must be a postive number")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + amount, user_id)
        flash("Deposited!")
        return redirect("/")
    else:
        return render_template("deposit.html")