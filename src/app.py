from flask import Flask, flash, session, render_template, request, redirect, url_for, make_response
import pyrebase
import sys
import os
from dotenv import load_dotenv
# datetime for greetings
from datetime import datetime, timedelta
# api functions
from apicalls import company_info, company_news, stock_quote

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

config = {
    'apiKey': os.getenv('FB_API_KEY'),
    'authDomain': os.getenv('FB_AUTH_DOMAIN'),
    'projectId': os.getenv('FB_PROJECT_ID'),
    'storageBucket': os.getenv('FB_SBUCKET'),
    'messagingSenderId': os.getenv('FB_SENDER_ID'),
    'appId': os.getenv('FB_APP_ID'),
    'measurementId': os.getenv('FB_MEAS_ID'),
    'databaseURL': os.getenv('FB_DB_URL')
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firebase.database()


# greeting goes based on server time so ignore this for now
# def generateGreeting():
#     # generate greeting base on current time       
#     curr_hr = datetime.now().hour
#     if curr_hr < 12:
#         greeting = 'Good morning,'
#     elif curr_hr <= 18:
#         greeting = 'Good afternoon,'
#     else:
#         greeting = 'Good evening,'
#     return greeting


@app.route('/', methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        username = email.split('@')[0]
        # try to sign in user
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = username
            return redirect(url_for('dashboard'))
        except:
            flash('Failed to login, please try again.', category='danger')
    return render_template('index.html')


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        username = email.split('@')[0]
        # attempt to create new user
        try:
            # check to see if user exists in database
            users = db.child("users").get()
            # if user doesn't exist in database add them
            if username not in users.val():
                user = auth.create_user_with_email_and_password(email, password)
                # add user to database
                db.child("users").child(username).set({'watchlist': ['temp']})
            elif username in users.val():
                flash(f'User already exists with email {email}', category='danger')
            return redirect(url_for('login'))
        except:
            flash('Failed to register user.', category='danger')
    return render_template('register.html')


@app.route('/passwordreset', methods=['GET', 'POST'])
def passwordreset():
    if request.method == 'POST':
        # send password reset email
        email = request.form.get('email')
        try:
            auth.send_password_reset_email(email)
            flash(f'Password reset email has been sent to {email}.', category='success')
            return redirect(url_for('login'))
        except:
            flash(f'Account not found with email {email}.', category='danger')
    return render_template('passwordreset.html')

@app.route('/logout')
def logout():
    if 'user' in session:
        session.pop('user')
    return redirect(url_for('login'))


@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    if 'user' in session:
        if request.method == 'POST':
            # add item to list
            ticker = request.form.get('ticker').upper()
            user_watch_list = db.child("users").child(session['user']).get().val()['watchlist']
            if 'temp' in user_watch_list:
                user_watch_list[0] = ticker
            elif ticker not in user_watch_list:
                # need to check its a valid ticker in api
                ticker_test = company_info(ticker)
                # if length of ticker_test is 0, then the ticker isn't supported by the api
                if len(ticker_test) != 0:
                    user_watch_list.append(ticker)
            # update list in db
            db.child("users").child(session['user']).set({'watchlist': user_watch_list})
        # get the users list
        user_watch_list = db.child("users").child(session['user']).get().val()['watchlist']
        # do api calls
        stock_info_dict = {}
        company_news_dict = {}
        if 'temp' not in user_watch_list:
            # could optimize this part so the api calls arent made everytime the page refreshes
            for idx, stock in enumerate(user_watch_list):
                if idx not in stock_info_dict:
                    # if the stock at idx i in watchlist is not already in stock info
                    stock_info_dict[idx] = 'temp'
                company_information = company_info(stock)
                stock_information = stock_quote(stock)
                company_news_list = company_news(stock)
                # check to see if the api returned anything
                if company_information:
                    stock_info_dict[idx] = company_information
                if stock_information:
                    #.update() appends to a dictionary
                    stock_info_dict[idx].update(stock_information)
                if company_news_list:
                    if stock not in company_news_dict:
                        company_news_dict[stock] = []
                    company_news_dict[stock] = company_news_list[:5]
            
            # before rendering, reverse order of stock_info_dict by index so that the most recently added item is first
            reversed_stock_info_dict = dict(sorted(stock_info_dict.items(), reverse=True))
            
        return render_template('dashboard.html', name=session['user'], stock_info=reversed_stock_info_dict, news_articles=company_news_dict) 
    
    return redirect(url_for('login'))


@app.route('/dashboard/delete/<int:item_id>', methods=['POST'])
def deleteItem(item_id):
    if 'user' in session:
        # item_id is the index of the stock to remove from the watchlist
        user_watch_list = db.child("users").child(session['user']).get().val()['watchlist']
        # check if deleteing makes watchlist None type, if so, set to ['temp']
        if len(user_watch_list) == 1:
            user_watch_list = ['temp']
        else:
            # delete item
            del user_watch_list[item_id]
        # update the watchlist
        db.child("users").child(session['user']).update({'watchlist': user_watch_list})
        
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(port=int(os.environ.get("PORT", 8080)),host='0.0.0.0',debug=True)