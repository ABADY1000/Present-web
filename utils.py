from hashlib import sha3_224
import re
from werkzeug.utils import secure_filename
from mysql.connector import connect
import functools
import datetime
# from flask import g
# from mysql.connector import connect, Error as SQLError
ALLOWED__USER_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg'}
#

def hash_password(passwd):
    return sha3_224(passwd.encode()).hexdigest()


def is_valid_name(name):
    return len(name) > 0 and re.match("^[a-zA-Z\u0621-\u064A]*$", name) is not None


def is_valid_password(passwd):
    return len(passwd) >= 5 and re.match("^[a-zA-Z0-9~!@#$%^&*\\-+]*$", passwd) is not None


def is_valid_email(email):
    """Regex source https://www.geeksforgeeks.org/check-if-email-address-valid-or-not-in-python/ """
    return re.match('^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$', email) is not None


def is_valid_code(code):
    return len(code) > 0 and re.match("^[a-zA-Z0-9]*$", code) is not None

def is_valid_time(time):
    return len(time) >0 and re.match("^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", time) is not None


def allowed_user_photo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED__USER_PHOTO_EXTENSIONS


def subscription_end_data(typ):
    if typ == "STANDARD":
        return datetime.date.today()+datetime.timedelta(days=30*6)
    elif typ == "PREMIUM":
        return datetime.date.today()+datetime.timedelta(days=360)
    else:
        return datetime.date.today()+datetime.timedelta(days=30*2)


def database_access(func):
    from flask import g
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'dbc' not in g:
            g.db_connection = connect(host="localhost", user="hadhir", passwd="kau2020", database="hadhir")
            g.dbc = g.db_connection.cursor()
            r = func(*args, **kwargs)
            g.dbc.close()
            g.db_connection.close()
            g.pop("db_connection")
            g.pop("dbc")
            return r
    return wrapper


def restrict_access(access, account_type=None):
    if access not in {"public", "private"} and account_type not in {None, "institute", "instructor", "student"}:
        raise ValueError("Illegal arguments passed to the account_access decorator")
    from flask import session, redirect, url_for
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if access == "public" and "account" in session:
                return redirect(url_for("dashboard"))
            if access == "private" and "account" not in session:
                return redirect(url_for("index"))
            if access == "private" and account_type is not None and account_type != session["account"]["account_type"]:
                return redirect(url_for("dashboard"))
            return func(*args, **kwargs)
        return wrapper
    return decorator




