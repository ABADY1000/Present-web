from flask import Flask, session, jsonify, redirect, url_for, abort, request, render_template as flask_render_template
from flask import make_response, g
# import face_recognition
import json
import os
import sys
from mysql.connector import connect, Error as SQLError
from utils import *
from image_utils import *
import uuid
from datetime import datetime


UPLOAD_FOLDER = '/websites.private/hadhir/user-photos'
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 2**20  # Limit upload size to 32 MB

LOCALE_FILE_MAPPING = {"عربي": "arabic", "English": "english"}


def render_template(file_name, **context):
    global locale
    # Use locale from cookies or use default.
    locale_file_name = "arabic"
    if "locale" in request.cookies:
        locale_file_name = request.cookies["locale"]
    with app.open_resource("static/locale/{}.json".format(locale_file_name)) as f:
        locale = json.load(f)
    if file_name in locale:
        context.update(locale[file_name])
    # Add common values as well
    for k, v in locale.items():
        if k.startswith("common/"):
            context.update(v)
    # insert error in context if its found in session and consume it
    if "error" in session:
        context["error"] = context["_error_" + session["error"]]
        del session["error"]
    context["_locale_display"] = locale["_locale_display"]
    context["local"]=locale_file_name
    return flask_render_template(file_name, **context)


def put_error(msg):
    session["error"] = msg


@app.route("/index")
@app.route("/")
@restrict_access(access="public")
def index():
    if request.method == "GET":
        if "locale" in request.cookies:
            return render_template("index.html")
        else:
            return render_template("index.html", locale=request.cookies.get("locale"))


@app.route("/change-locale")
def change_locale():
    locale_file_name = "arabic"
    if "locale" in request.cookies:
        locale_file_name = request.cookies["locale"]
    if locale_file_name == "arabic":
        locale_file_name = "english"
    else:
        locale_file_name = "arabic"
    resp = redirect(url_for("index"))
    resp.set_cookie("locale", locale_file_name, max_age=60*60*24*365*1)
    return resp


# TODO avoid duplicate email and pass for user and institute
@app.route("/login", methods=["POST", "GET"])
@restrict_access(access="public")
@database_access
def login():
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        g.dbc.execute("SELECT user_id, user_account_type,user_activation from USER WHERE "
                      "user_email=%s AND user_password=%s",
                    [request.form["login-email"], hash_password(request.form["login-password"])])
        account = g.dbc.fetchall()
        found_in_user = True
        if len(account)> 0 and not(account[0][2]):
            return redirect(url_for("login", value_error="wait_activation"))
        if len(account) == 0:  # If not found in user table, look in the institute table
            g.dbc.execute("SELECT institute_id from INSTITUTE WHERE institute_email=%s AND institute_password=%s",
                        [request.form["login-email"], hash_password(request.form["login-password"])])
            account = g.dbc.fetchall()
            found_in_user = False
        if len(account) == 0:  # If neither found in user nor institute tables
            put_error("invalid_credentials")
            return redirect(url_for("login"))
        if found_in_user:
            keys = ("id", "account_type")
            account = dict(zip(keys, account[0]))
        else:
            keys = ("id",)
            account = dict(zip(keys, account[0]))
            account["account_type"] = "institute"
        session["account"] = account
        return redirect(url_for("dashboard"))


@app.route("/logout")
@restrict_access(access="private")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/register", methods=["POST", "GET"])
@restrict_access(access="public")
@database_access
def register():
    if request.method == "GET":
        if "successful_registration" in session:
            session.pop("successful_registration")
            return render_template("register.html", successful_registration=True)
        else:
            return render_template("register.html", successful_registration=False)
    elif request.method == "POST":
        def error_redirect(error):
            put_error(error)
            return redirect(url_for("register"))
        # Syntax Check
        if not is_valid_name(request.form["first-name"]):
            return error_redirect("first_name")
        if not is_valid_name(request.form["last-name"]):
            return error_redirect("last_name")
        if not is_valid_email(request.form["email"]):
            return error_redirect("email")
        if not is_valid_password(request.form["password"]):
            return error_redirect("password")
        if not is_valid_code(request.form["institute-code"]):
            return error_redirect("institute_code")
        # Value Check
        # TODO Should we individually check if institute exists or email exists or leave that for the database ?
        try:
            g.dbc.execute("SELECT institute_id from INSTITUTE where institute_registration_code=%s",
                        [request.form["institute-code"]])
            result = g.dbc.fetchall()
            if len(result) == 0:
                return error_redirect("institute_not_found")
            else:
                institute_key = result[0][0]
            g.dbc.execute("SELECT user_email from USER where user_email=%s", [request.form["email"]])
            if len(g.dbc.fetchall()) != 0:
                return error_redirect("email_exists")
            # Insert
            g.dbc.execute("insert into USER "
                        "(user_first_name,user_last_name,user_email,user_password,user_account_type,user_institute,"
                        "user_institute_id) values(%s,%s,%s,%s,%s,%s,%s)",
                        [request.form["first-name"], request.form["last-name"], request.form["email"],
                         hash_password(request.form["password"]), request.form["type"], institute_key,
                         request.form["institute-id"]])
            g.db_connection.commit()
            #select the id if this user
            g.dbc.execute("select user_id from user where user_email=%s",[request.form["email"]])
            user_id=g.dbc.fetchall()[0][0]
            # upload files
            user_photos = [request.files['file0'],request.files['file1'],request.files['file2']]
            for file in user_photos:
                if len(file.filename) > 0:
                    if not allowed_user_photo(file.filename):
                        return error_redirect("user_photo_filename")
                    filename = "{}".format(user_id)+"_"+uuid.uuid4().hex
                    file_path = os.path.join(app.config['UPLOAD_FOLDER']+"/"+filename+".png")
                    file.save(file_path)
                    img1 = face_recognition.load_image_file(app.config['UPLOAD_FOLDER']+"/"+filename+".png")
                    encoding = face_recognition.face_encodings(img1)

                    if len(encoding) == 1:
                        path=os.path.join(app.config['UPLOAD_FOLDER'],filename+".json")
                        with open(path, "w") as f:
                            json.dump(list(encoding[0]),f)
                        g.dbc.execute("insert into user_image_paths values(%s,%s)",[user_id,filename])
                    else:
                        g.dbc.execute("delete from user where user_id=%s",[user_id])
                        g.db_connection.commit()
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename+".png"))
                        return error_redirect("invalid_photo")

            g.db_connection.commit()

        except SQLError as e:
            print(e, file=sys.stderr)
            return error_redirect("unknown")
        session["successful_registration"] = True
        return redirect(url_for("register"))


@app.route('/edit-user', methods=['GET','POST'])
@restrict_access(access="private")
@database_access
def edit_user():
    id = session["account"]["id"]
    if request.method == 'GET':
        try:
            # fetch user info
            g.dbc.execute("select user_first_name, user_last_name, user_email"
                        ", user_account_type, institute_name,user_institute_id"
                        " from USER,INSTITUTE where user_id =%s and user_institute=institute_id ",[id])
            result = g.dbc.fetchall()

            if len(result) > 0:
                context = dict()
                context["user_first_name"] = result[0][0]
                context["user_last_name"] = result[0][1]
                context["user_email"] = result[0][2]
                context["user_account_type"] = result[0][3]
                context["institute_name"] = result[0][4]
                context["user_institute_id"] = result[0][5]
                context["edit"] = True

                return render_template("register.html",**context)
            else:
                return redirect(url_for('edit_user', value_error="user_id"))
        except SQLError as error:
            print(error)
            return redirect(url_for('edit_user', value_error="sql_error"))
    elif request.method == 'POST':
        user_first_name = request.form["first-name"]
        user_last_name = request.form["last-name"]
        user_email = request.form["email"]
        user_old_password = request.form["user-old-password"]
        user_new_password = request.form["user-new-password"]
        user_photo = request.files["user-photo"]

        if user_old_password != "" and user_new_password != "":
            # fetch user old password
            try:
                g.dbc.execute("select user_password from USER where user_id =%s ", [id])
                result = g.dbc.fetchall()
                if len(result)>0:
                    if result[0][0] == hash_password(user_old_password):
                        g.dbc.execute("UPDATE USER set user_password = %s where user_id = %s",
                                    [hash_password(user_new_password),id])
                        g.db_connection.commit()
                    else:
                        return redirect(url_for('edit_user', value_error = "wrong_old_password"))
                else:
                    return redirect(url_for('edit_user', value_error = "wrong_institute_id"))

            except SQLError as error:
                print(error)
                return redirect(url_for('edit_user',value_error="sql_error"))
        if len(user_photo.filename) > 0:  # FIXME Is there a better way to check if a file was uploaded ?
            try:
                g.dbc.execute("select user_photo_path from USER where user_id = %s",[id])
                result=g.dbc.fetchall()
                if result[0][0] != 'NULL':  # if len(result)>0 : will return true if the value of path is null
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], result[0][0]))
                if not allowed_user_photo(user_photo.filename):
                    return redirect(url_for('edit_user', value_error = "user_photo_filename"))
                filename = uuid.uuid4().hex
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                user_photo.save(file_path)
                g.dbc.execute("UPDATE USER set user_photo_path = %s where user_id = %s",
                            [filename, id])
                g.db_connection.commit()
                # else:
                #     redirect(url_for('edit_user', value_error="wrong_photo_path"))
            except SQLError as error:
                print(error)
                return redirect(url_for('edit_user', value_error = "sql_error_update_photo"))

        g.dbc.execute("UPDATE  USER set user_first_name=%s, user_last_name=%s, user_email=%s"
                    "where user_id=%s",
                    [user_first_name, user_last_name,user_email, id])
        g.db_connection.commit()
        return redirect(url_for('dashboard'))


@app.route('/delete-user',methods=['POST'])
@restrict_access(access="private")
@database_access
def delete_user():
    id = session["account"]["id"]
    try:
        g.dbc.execute("DELETE from USER where user_id = %s",[id])
        g.db_connection.commit()
        return redirect(url_for('logout'))
    except SQLError as error:
        print(error)
        redirect(url_for('edit-user',value_error="sql_error_in delete"))


@app.route("/institute-register", methods=["POST", "GET"])
@restrict_access(access="public")
@database_access
def institute_register():
    if request.method == "GET":
        if "successful_registration" in session:
            session.pop("successful_registration")
            return render_template("institute-register.html", successful_registration=True)
        else:
            if "package" in request.args:
                return render_template("institute-register.html",
                                       premium="selected" if request.args.get("package") == "premium" else "",
                                       standard="selected" if request.args.get("package") == "standard" else "",
                                       free="selected" if request.args.get("package") == "free" else "",
                                       successful_registration=False)
            else:
                return render_template("institute-register.html",premium="selected", standard="", free="",
                                       successful_registration=False)
    elif request.method == 'POST':
        try:
            institute_name = request.form["institute-name"]
            institute_email = request.form["institute-email"]
            institute_password = request.form["institute-password"]
            subscription_type = request.form["institute-subscription"]
            subscription_end = subscription_end_data(subscription_type)
            registration_code = (str(uuid.uuid4())[:5])
            # check for exist institute
            g.dbc.execute("select * from INSTITUTE where institute_email =%s ", [institute_email])
            result = g.dbc.fetchall()
            if len(result) > 0:
                return redirect(url_for('institute_register', value_error = "institute_exist"))
            else:
                # insert new institute
                g.dbc.execute("insert into INSTITUTE"
                            "(institute_name, institute_email, institute_password, institute_subscription,"
                            "institute_subscription_end, institute_registration_code)"
                            "values (%s,%s,%s,%s,%s,%s)",
                            [institute_name, institute_email, hash_password(institute_password), subscription_type
                                , subscription_end, registration_code])
                g.db_connection.commit()
                session["successful_registration"] = True
                return redirect(url_for("institute_register"))
        except SQLError as error:
            print(error)
            return redirect(url_for('institute_register', value_error="sql_error"))
        except Exception as e:
            print(e)
            return redirect(url_for('institute_register', value_error = "bind_request_error"))


@app.route('/edit-institute', methods=['GET','POST'])
@restrict_access(access="private", account_type="institute")
@database_access
def edit_institute():
    id = session["account"]["id"]
    if request.method == 'GET':
        try:
            # fetch user info
            g.dbc.execute("select institute_name, institute_email, institute_subscription, institute_registration_code"
                            " from INSTITUTE where institute_id =%s ",[id])
            result = g.dbc.fetchall()
            if len(result) > 0:
                context = dict()
                context["institute_name"] = result[0][0]
                context["institute_email"] = result[0][1]
                context["institute_subscription"] = result[0][2]
                context["institute_code"] = result[0][3]
                context["edit"] = True

                return render_template("institute-register.html",**context)
            else:
                return redirect(url_for('edit_institute', value_error = "institute_id"))
        except SQLError as error:
            print(error)
            return redirect(url_for('edit_institute', value_error = "sql_error"))
    elif request.method == 'POST':
        institute_name = request.form["institute-name"]
        institute_email = request.form["institute-email"]
        institute_old_password = request.form["institute-old-password"]
        institute_new_password = request.form["institute-new-password"]

        if institute_old_password != "" and institute_new_password !="":
            # fetch user old password
            try:
                g.dbc.execute("select institute_password from INSTITUTE where institute_id =%s ", [id])
                result = g.dbc.fetchall()
                if len(result)>0:
                    if result[0][0] == hash_password(institute_old_password):
                        g.dbc.execute("UPDATE INSTITUTE set institute_password = %s where institute_id = %s",
                                    [hash_password(institute_new_password),id])
                        g.db_connection.commit()
                    else:
                        return redirect(url_for('edit_institute', value_error = "wrong_old_password"))
                else:
                    return redirect(url_for('edit_institute', value_error = "wrong_institute_id"))

            except SQLError as error:
                print(error)
                return redirect(url_for('edit_institute',value_error="sql_error"))

        g.dbc.execute("UPDATE INSTITUTE set institute_name = %s, institute_email=%s where institute_id = %s",
                    [institute_name,institute_email, id])
        g.db_connection.commit()
        return redirect(url_for('dashboard'))


@app.route('/delete-institute',methods=['POST'])
@restrict_access(access="private", account_type="institute")
@database_access
def delete_institute():
    id = session["account"]["id"]
    try:
        g.dbc.execute("DELETE from INSTITUTE where institute_id = %s",[id])
        g.db_connection.commit()
        return redirect(url_for('logout'))
    except SQLError as error:
        print(error)
        redirect(url_for('edit-institute',value_error="sql_error_in delete"))


@app.route("/contact-us")
@restrict_access(access="public")
def contact_us():
    return render_template("contact-us.html")


@app.route('/dashboard')
@restrict_access(access="private")
@database_access
def dashboard():
    context = dict()
    account_type = session["account"]["account_type"]
    template = "dashboard/{}-dashboard.html".format(account_type)
    id=session["account"]["id"]
    if account_type == "institute":
        try:
            context["show_profile_image"] = False
            # fetch institute name
            g.dbc.execute("SELECT institute_name from INSTITUTE where institute_id=%s", [id])
            context["account_name"] = g.dbc.fetchall()[0][0]
            session["account_name"]= context["account_name"]

            # fetch institute users
            g.dbc.execute("select user_id,user_institute_id, user_first_name, user_last_name"
                          ", user_email,user_account_type, user_activation"
                          "  from USER where user_institute=%s",[id])
            context['institute_users']=g.dbc.fetchall()

            # calculate the percentage of attendance for each user
            lectures=list()
            attend=list()
            for i in range(len(context["institute_users"])):
                g.dbc.execute("select lecture_record_id"
                              " from lecture_record, enrolled_in where "
                              "enrolled_in_section = lecture_record_section and enrolled_in_user=%s"
                              , [context["institute_users"][i][0]])
                result = g.dbc.fetchall()
                if len(result) > 0:
                    lectures.append(len(result))
                else:
                    lectures.append('0')

                g.dbc.execute("select attended_user from attended "
                              "where attended_lecture in "
                              "(select lecture_record_id from lecture_record, enrolled_in where"
                              " enrolled_in_section = lecture_record_section and enrolled_in_user=%s)"
                              " and attended_user =%s"
                              , [context["institute_users"][i][0],context["institute_users"][i][0]])
                result = g.dbc.fetchall()
                if len(result) > 0 and lectures[i] > 0:
                    attend.append("{0:.2f} %".format((len(result)/lectures[i])*100))
                else:
                    attend.append("{} %".format(0.00))

            context["attend_user"]=attend

            # fetch institute sections
            g.dbc.execute("select section_id, section_number, section_course_number, section_course_name "
                          ",user_first_name,user_last_name,count(enrolled_in_user)"
                          " from SECTION left join ENROLLED_IN on enrolled_in_section = section_id "
                          "inner join User on user_id = section_instructor     "
                          " where section_institute = %s group by section_id",[id])
            context["institute_sections"]=g.dbc.fetchall()

            # calculate the percentage of attendance section
            attend_section=list()
            total_attend=list()
            for i in range(len(context["institute_sections"])):
                section_att = section_attendance(context["institute_sections"][i][0])
                # print(section_att)
                attend_section.append("{0:.2f} %".format(section_att))
                total_attend.append(section_att)

            context["attend_section"]= attend_section

            # calculate total attendance of institute
            if len(total_attend) >0:
                context["total_attend"]="{0:.1f} %".format(sum(total_attend)/len(total_attend))
                context["attend_circle"]= (sum(total_attend)/len(total_attend))/100
            else:
                context["total_attend"] = "{0:.1f} %".format(0.00)
                context["attend_circle"] = 0.00



            # calculate number of instructor in institute
            g.dbc.execute("select count(*) from user where user_account_type='instructor' and user_institute=%s and user_activation=1" ,[id])
            context["num_instructor"]=g.dbc.fetchall()[0][0]
            # calculate number of student in institute
            g.dbc.execute("select count(*) from user where user_account_type='student' and user_institute=%s and user_activation=1", [id])
            context["num_student"] = g.dbc.fetchall()[0][0]

            # fetch institute classroom
            g.dbc.execute("select classroom_id,classroom_number, camera_id, camera_state, max(lecture_record_active) from classroom, lecture_record where classroom_institute=%s and lecture_record_classroom=classroom_id group by classroom_id",[id])
            context["institute_classrooms"]= g.dbc.fetchall()
            g.dbc.execute("select classroom_id,classroom_number, camera_id, camera_state from classroom where classroom_id not in (select classroom_id from classroom ,lecture_record where lecture_record_classroom=classroom_id) and classroom_institute=%s",[id])
            context["other_classroom"]=g.dbc.fetchall()
            

        except SQLError as error:
            print(error)
            return redirect(url_for('dashboard',value_error= 'sql_error_retrieve_data'))
    elif account_type in {"instructor", "student"}:
        context["show_profile_image"] = False
        try:
            g.dbc.execute("SELECT user_first_name, user_last_name, user_photo_path from USER where user_id=%s",
                          [session["account"]["id"]])
            result = g.dbc.fetchall()[0]
            context["account_name"] = "{} {}".format(result[0], result[1])
            session["account_name"] = context["account_name"]
            if result[2] is not None and result[2] != "" and result[2] != "NULL":
                context["account_image"] = get_image_data_url(os.path.join(
                    app.config['UPLOAD_FOLDER'], result[2]))
            else:
                context["account_image"] = url_for("static", filename="resources/images/profile-placeholder.png")
            if account_type == "instructor":
                # fetch instructor sections
                g.dbc.execute("select section_id, section_number, section_course_number, section_course_name ,count(*)"
                              " from SECTION left join ENROLLED_IN on enrolled_in_section = section_id"
                              " where section_instructor = %s group by section_id", [id])
                context["instructor_sections"] = g.dbc.fetchall()

                # calculate the percentage of attendance section
                attend_section = list()
                total_attend = list()
                for i in range(len(context["instructor_sections"])):
                    section_att = section_attendance(context["instructor_sections"][i][0])
                    attend_section.append("{0:.2f} %".format(section_att))
                    total_attend.append(section_att)
                context["attend_section"] = attend_section

                # calculate total attendance of institute
                if len(total_attend) > 0:
                    context["total_attend"] = "{0:.1f} %".format(sum(total_attend) / len(total_attend))
                    context["attend_circle"] = (sum(total_attend) / len(total_attend)) / 100
                else:
                    context["total_attend"] = "{0:.1f} %".format(0.00)
                    context["attend_circle"] = 0.00

            elif account_type == "student":
                # fetch student sections
                g.dbc.execute("select section_id, section_number, section_course_number, section_course_name,"
                              " user_first_name,user_last_name from SECTION"
                              " inner join User on user_id = section_instructor "
                              "inner join enrolled_in on enrolled_in_user = %s and enrolled_in_section =section_id", [id])
                context["student_sections"] = g.dbc.fetchall()

                # calculate the percentage of attendance section
                attend_section = list()
                total_attend = list()
                for i in range(len(context["student_sections"])):
                    student_att= student_attendance(context["student_sections"][i][0])

                    attend_section.append("{0:.2f} %".format(student_att))
                    total_attend.append(student_att)

                context["attend_section"] = attend_section

                # calculate total attendance of institute
                context["total_attend"] = "{0:.1f} %".format(sum(total_attend) / len(total_attend))
                context["attend_circle"] = (sum(total_attend) / len(total_attend)) / 100
            else:
                return redirect(url_for('dashboard', value_error='type_error'))

        except SQLError as error:
            print(error)
            return redirect(url_for('dashboard', value_error='sql_error_retrieve_data'))

    else:
        return redirect(url_for("index", error="invalid_session"))
    return render_template(template, **context)


def section_attendance(id):
    try:
        g.dbc.execute("select count(*) from lecture_record where lecture_record_section=%s"
                      , [id])
        num_lectures = g.dbc.fetchall()[0][0]
        g.dbc.execute("select count(*) from enrolled_in where enrolled_in_section =%s"
                      , [id])
        num_student = g.dbc.fetchall()[0][0]
        g.dbc.execute("select count(*) from attended where attended_lecture in "
                      "(select lecture_record_id  from lecture_record where lecture_record_section=%s)"
                      , [id])
        num_attend = g.dbc.fetchall()[0][0]
        if num_lectures > 0 and num_student >0:
            return (num_attend / (num_lectures * num_student)) * 100
        else:
            return 0.00
    except SQLError as error:
        print(error)


def student_attendance(id):
    try:
        g.dbc.execute("select count(*) from lecture_record where lecture_record_section=%s"
                      , [id])
        num_lectures = g.dbc.fetchall()[0][0]

        g.dbc.execute("select count(*) from attended where attended_lecture in "
                      "(select lecture_record_id  from lecture_record where lecture_record_section=%s) "
                      "and attended_user=%s"
                      , [id, session["account"]["id"]])
        num_attend = g.dbc.fetchall()[0][0]
        if num_lectures > 0:
            return (num_attend / (num_lectures)) * 100

        else:
            return 0.00
    except SQLError as error:
        print(error)



@app.route('/activate-user/<int:id>')
@restrict_access(access="private", account_type="institute")
@database_access
def activate_user(id):
    try:
        g.dbc.execute("update user set user_activation=1 where user_id =%s and user_institute=%s",[id,session["account"]["id"]])
        g.db_connection.commit()

        return redirect(url_for('dashboard'))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard',error="sql error"))


@app.route('/deactivate-user/<int:id>')
@restrict_access(access="private", account_type="institute")
@database_access
def deactivate_user(id):
    try:
        g.dbc.execute("delete from user where user_id =%s and user_institute=%s", [id,session["account"]["id"]])
        g.db_connection.commit()
        return redirect(url_for('dashboard'))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql error"))


@app.route('/class-details/<int:id>')
@restrict_access(access="private", account_type="institute")
@database_access
def class_details(id):
    session["classroom_id"]=id
    context=dict()
    try:
        g.dbc.execute("select classroom_number,camera_id,camera_state from classroom where classroom_id=%s and "
                      "classroom_institute=%s",[id,session["account"]["id"]])
        result=g.dbc.fetchall()[0]
        context["class_number"]=result[0]
        context["camera_ip"]=result[1]
        context["camera_status"]=result[2]
        if result[2] == "online":
            context["status_color"]="var(--theme-primary)"
        else:
            context["status_color"] = "var(--theme-reject)"

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        #
        g.dbc.execute("select section_course_name,user_first_name,user_last_name,"
                      " lecture_record_end from lecture_record,section,user "
                      "where lecture_record_active=1 and section_id=lecture_record_section and user_id=section_instructor")
        result=g.dbc.fetchall()
        if len(result) > 0:
            context["course_name"]=result[0][0]
            context["course_instructor"]=result[0][1] +" "+result[0][2]
            context["remaining"]=datetime.strptime(result[0][3], "%H:%M") - datetime.strptime(current_time, "%H:%M")

        return render_template("dashboard/details/class.html",**context)
        # return jsonify({"classroom_num":result[0][0],"camera_num":result[0][1]})
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql_error"))
    except Exception as error:
        print(error)
        return redirect(url_for('dashboard', error="error"))


@app.route('/class-add',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def class_add():
    id= session["account"]["id"]
    try:
        class_number=request.form["class-number"]
        camera_number=request.form["camera-number"]

        g.dbc.execute("select classroom_number from classroom where classroom_number=%s and classroom_institute=%s"
                      ,[class_number,session["account"]["id"]])
        result= g.dbc.fetchall()

        if len(result) > 0:
            return redirect(url_for('dashboard',error="class_found"))
        else:
            g.dbc.execute("insert into classroom(classroom_number,camera_id,camera_state,classroom_institute)"
                          "values (%s,%s,%s,%s)",[class_number,camera_number,"online",id])
            g.db_connection.commit()
            return redirect(url_for('dashboard'))

    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql error"))
    except Exception as e:
        print(e)
        return redirect(url_for('dashboard', error="sql error"))


@app.route('/class-edit',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def class_edit():
    try:
        clssroom_num=request.form["class-number"]
        camera_num=request.form["camera-number"]
        if "classroom_id" in session:
            g.dbc.execute("update classroom set classroom_number=%s,camera_id=%s where classroom_id =%s "
                          "and classroom_institute=%s",
                          [clssroom_num,camera_num,session["classroom_id"],session["account"]["id"]])
            g.db_connection.commit()
            session.pop('classroom_id', None)
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('dashboard', error="session_error"))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql_error"))
    except Exception as error:
        print(error)
        return redirect(url_for('dashboard', error="error"))


@app.route('/class-delete')
@restrict_access(access="private", account_type="institute")
@database_access
def class_delete():
    try:
        if "classroom_id" in session:
            g.dbc.execute("delete from classroom where classroom_id =%s and classroom_institute=%s",
                          [session["classroom_id"],session["account"]["id"]])
            g.db_connection.commit()
            session.pop('classroom_id', None)
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('dashboard',error="session_error"))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql_error"))
    except Exception as error:
        print(error)
        return redirect(url_for('dashboard', error="error"))


@app.route('/section-details/<int:id>')
@restrict_access(access="private")
@database_access
def section_details(id):
    session["section_id"] = id
    context = dict()
    if session["account"]["account_type"] == "student":
        pre=student_attendance(id)
    else:
        pre=section_attendance(id)

    context["attend_section"] = "{0:.2f} %".format(pre)
    session["section_pre"]="{0:.2f} %".format(pre)
    context["attend_circle"] = pre/100
    context["account_name"]=session["account_name"]
    try:
        #ensure that this user can access this section
        g.dbc.execute("select section_instructor,section_institute from section where section_id=%s",[id])
        is_valid=g.dbc.fetchall()[0]
        if session["account"]["account_type"] == "institute" and is_valid[1] != session["account"]["id"]:
            return redirect(url_for('dashboard', value_error="section_found"))
        if session["account"]["account_type"] == "instructor" and is_valid[0] != session["account"]["id"]:
            return redirect(url_for('dashboard', value_error="section_found"))

        g.dbc.execute("select * from enrolled_in where enrolled_in_user=%s and enrolled_in_section=%s"
                      ,[session["account"]["id"], id])
        is_valid_student=g.dbc.fetchall()
        if len(is_valid_student) < 1 and session["account"]["account_type"] == "student":
            return redirect(url_for('dashboard', value_error="section_found"))

        # fetch section info
        g.dbc.execute('select section_number,section_course_number,section_course_name,user_first_name,'
                    'user_last_name,section_instructor from SECTION,USER where '
                    'section_id= %s and user_id=section_instructor ', [id])
        section_info = g.dbc.fetchall()
        context["section_info"] =section_info

        if len(section_info) > 0:

            # fetch section schedule
            g.dbc.execute('select lecture_schedule_id ,classroom_number,lecture_schedule_start,'
                          'lecture_schedule_end,lecture_schedule_day from LECTURE_SCHEDULE,classroom'
                          ' where lecture_schedule_section = %s and classroom_id = lecture_schedule_classroom',[id])
            context["section_schedule"]=g.dbc.fetchall()


            # fetch students in lecture
            g.dbc.execute('select user_id, user_institute_id,user_first_name,user_last_name,user_email from'
                          ' USER, ENROLLED_IN where enrolled_in_section = %s and user_id = enrolled_in_user and'
                          ' user_account_type="student"',[id])
            context["section_students"]= g.dbc.fetchall()

            # fetch lecture records
            g.dbc.execute('select lecture_record_id,lecture_record_date,lecture_record_start ,lecture_record_end from '
                          'LECTURE_RECORD where lecture_record_section = %s',[id])
            context["section_records"] = g.dbc.fetchall()
            if session["account"]["account_type"]=="student":
                attend=list()
                for i in range(len(context["section_records"])):
                    g.dbc.execute("select* from attended where attended_user=%s and attended_lecture=%s"
                                  ,[session["account"]["id"],context["section_records"][i][0]])
                    result=g.dbc.fetchall()
                    if len(result) > 0:
                        attend.append(True)
                    else:
                        attend.append(False)
                context["attend"]=attend

            # fetch all instructors in institute
            g.dbc.execute("select user_id,user_first_name,user_last_name from USER "
                          "where user_institute= %s and user_account_type='instructor' and user_activation=1", [session["account"]["id"]])
            context["instructors"]=g.dbc.fetchall()

            # calculate percentage of attendance of lecture and students
            lecture_attend=list()
            student_attend=list()

            if len(context["section_students"]) >0:
                total_enrolled = len(context["section_students"])
                for i in range(len(context["section_records"])):
                    g.dbc.execute("select count(*) from attended where attended_lecture=%s",
                                  [context["section_records"][i][0]])
                    result = g.dbc.fetchall()

                    if len(result)>0:
                        lecture_attend.append("{0:.2f} %".format((result[0][0]/total_enrolled)*100))
                    else:
                        lecture_attend.append("{0:.2f} %".format(0.00))
            else:
                total_enrolled=0

            context["total_enrolled"]=total_enrolled
            context["lecture_attend"]=lecture_attend

            if len(context["section_records"])>0:
                total_lecture= len(context["section_records"])
                for i in range(len(context["section_students"])):
                    g.dbc.execute("select count(*) from attended where attended_user=%s and attended_lecture in ("
                                  "select lecture_record_id from LECTURE_RECORD where lecture_record_section = %s)"
                                  ,[context["section_students"][i][0],id])
                    result=g.dbc.fetchall()
                    if len(result)> 0:
                        student_attend.append("{0:.2f} %".format((result[0][0]/total_lecture)*100))
                    else:
                        student_attend.append("{0:.2f} %".format(0.00))
            else:
                total_lecture=0

            context["total_lecture"]=total_lecture
            context["student_attend"]=student_attend

            #get the day name with each lang
            locale_file_name = "arabic"
            if "locale" in request.cookies:
                locale_file_name = request.cookies["locale"]
            with app.open_resource("static/locale/{}.json".format(locale_file_name)) as f:
                locale = json.load(f)

            context["days"]=locale["days"]

            return render_template('dashboard/details/section.html',**context)
        else:
            return redirect(url_for('dashboard',value_error="section_found"))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', value_error="sql_error"))


@app.route('/section-add', methods=['GET', 'POST'])
@restrict_access(access="private", account_type="institute")
@database_access
def section_add():

    if request.method == 'GET':
        try:
            # fetch all instructors in institute
            g.dbc.execute("select user_id,user_first_name,user_last_name from user "
                          "where user_institute= %s and user_account_type='instructor' and user_activation=1"
                        , [session["account"]["id"]])
            result = g.dbc.fetchall()
            return jsonify({"instructors" : result})
        except SQLError as error:
            print(error)
            return jsonify({"error": error})

    elif request.method == 'POST':
        # bind form data with variable
        try:
            section_number = request.form["section-number"]
            course_number = request.form["course-number"]
            course_name = request.form["course-name"]
            section_instructor = request.form["section-instructor"]

            # is this section exist
            g.dbc.execute("select * from SECTION where section_number = %s and section_institute=%s",[section_number,session["account"]["id"]])
            result= g.dbc.fetchall()

            if len(result) > 0:
                return redirect(url_for("section_add", value_error="section_found"))
            else:
                g.dbc.execute("insert into SECTION(section_number,section_course_number,section_course_name,"
                              "section_instructor,section_institute) values (%s,%s,%s,%s,%s)",
                              [section_number, course_number, course_name, section_instructor,
                               session["account"]["id"]])
                g.db_connection.commit()

                return redirect(url_for("dashboard"))

        except SQLError as error:
            print(error)
            return redirect(url_for("section_add", value_error="sql_error"))
        except Exception as e:
            print(e)
            return redirect(url_for("section_add", value_error="request_error"))


@app.route('/section-edit',methods=['POST'])
@restrict_access(access="private",account_type="institute")
@database_access
def section_edit():
    # bind form data with variable
    try:
        section_number = request.form["section-number"]
        course_number = request.form["course-number"]
        course_name = request.form["course-name"]
        section_instructor = request.form["section-instructor"]

        g.dbc.execute("update SECTION set section_number=%s, section_course_number=%s,section_course_name=%s"
                      ",section_instructor=%s where section_id=%s",
                      [section_number, course_number, course_name, section_instructor,session["section_id"]])
        g.db_connection.commit()
        session.pop("section_id")
        session.pop("section_pre")

        return redirect(url_for("dashboard"))

    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", value_error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(url_for("section_details", value_error="request_error"))


@app.route('/section-delete',methods=['POST'])
@restrict_access(access="private", account_type="institute")
@database_access
def section_delete():
    try:
        g.dbc.execute("delete from section where section_id=%s",[session["section_id"]])
        g.db_connection.commit()

        session.pop("section_id")
        session.pop("section_pre")

        return redirect(url_for("dashboard"))

    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", value_error="sql_error"))


@app.route('/lecture-schedule-details/<int:id>')
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_schedule_details(id):
    if not(session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    session["schedule_id"]=id
    try:
        g.dbc.execute('select classroom_number,lecture_schedule_start,'
                      'lecture_schedule_end,lecture_schedule_day from LECTURE_SCHEDULE,classroom'
                      ' where lecture_schedule_id = %s and classroom_id = lecture_schedule_classroom', [id])
        info=g.dbc.fetchall()

        g.dbc.execute("select classroom_id, classroom_number from classroom where classroom_institute=%s",[session["account"]["id"]])
        classrooms=g.dbc.fetchall()

        days=["Saturday","Sunday","Monday","Tuesday","Wednesday","Thursday","Friday"]

        locale_file_name = "arabic"
        if "locale" in request.cookies:
            locale_file_name = request.cookies["locale"]
        with app.open_resource("static/locale/{}.json".format(locale_file_name)) as f:
            locale = json.load(f)

        return jsonify({"info" : info , "classrooms" : classrooms, "days" : days,"selected_day" :locale["days"]})
    except SQLError as error:
        print(error)
        return jsonify({"error": error})


@app.route('/lecture-schedule-add',methods=["GET","POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_schedule_add():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    if request.method == "GET":
        try:
            # fetch all classrooms in institute
            g.dbc.execute("select classroom_id ,classroom_number from classroom where classroom_institute=%s",[session["account"]["id"]])
            classrooms=g.dbc.fetchall()
            return jsonify({"classrooms" : classrooms})
        except SQLError as error:
            print(error)
            return jsonify({"error":error})

    elif request.method =="POST":
        try:
            start = request.form["start-time"]
            end=request.form["end-time"]
            day=request.form["day"]
            classroom=request.form["classroom"]

            if not (is_valid_time(start)):
                return redirect(url_for("section_details", id=session["section_id"], error="time_error"))

            if not (is_valid_time(end)):
                return redirect(url_for("section_details", id=session["section_id"], error="time_error"))

            g.dbc.execute("insert into lecture_schedule(lecture_schedule_classroom,"
                          "lecture_schedule_start,lecture_schedule_end,lecture_schedule_day,lecture_schedule_section)"
                          "values(%s,%s,%s,%s,%s)",
                          [classroom,start,end,day,session["section_id"]])
            g.db_connection.commit()
            return redirect(url_for("section_details",id=session["section_id"]))
        except SQLError as error:
            print(error)
            return redirect(url_for("section_details", id=session["section_id"],error="sql_error"))
        except Exception as e:
            print(e)
            return redirect(
                url_for("section_details", id=session["section_id"], error="error"))


@app.route('/lecture-schedule-edit',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_schedule_edit():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        start = request.form["start-time"]
        end = request.form["end-time"]
        day = request.form["day"]
        classroom = request.form["classroom"]

        if not (is_valid_time(start)):
            return redirect(
                url_for("section_details", id=session["section_id"], error="time_error"))

        if not (is_valid_time(end)):
            return redirect(
                url_for("section_details", id=session["section_id"], error="time_error"))

        g.dbc.execute("update lecture_schedule set lecture_schedule_start=%s, lecture_schedule_end=%s"
                      ", lecture_schedule_day=%s, lecture_schedule_classroom=%s where lecture_schedule_id =%s",
                      [start,end,day,classroom,session["schedule_id"]])
        g.db_connection.commit()
        return redirect(url_for("section_details",id=session["section_id"]))
    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", id=session["section_id"],error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(
            url_for("section_details", id=session["section_id"], error="error"))


@app.route('/lecture-schedule-delete',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_schedule_delete():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        g.dbc.execute("delete from lecture_schedule where lecture_schedule_id=%s",[session["schedule_id"]])
        g.db_connection.commit()
        return redirect(url_for("section_details", id=session["section_id"]))
    except SQLError as error:
        print(error)
        return redirect(
            url_for("section_details", id=session["section_id"], error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(
            url_for("section_details", id=session["section_id"], error="error"))


@app.route('/lecture-details/<int:id>')
@restrict_access(access="private")
@database_access
def lecture_details(id):
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    session["lecture_id"]=id
    try:
        # fetch lecture details
        g.dbc.execute("select lecture_record_id, lecture_record_classroom, lecture_record_start, lecture_record_end,"
                      " DATE_FORMAT(lecture_record_date, '%Y-%m-%d')from lecture_record where lecture_record_id=%s ",[id])
        lecture=g.dbc.fetchall()

        g.dbc.execute("select classroom_number from classroom where classroom_id =%s",[lecture[0][1]])
        classroom_ins=g.dbc.fetchall()[0][0]

        # fetch attended student
        g.dbc.execute("select user_id, user_institute_id, user_first_name,user_last_name "
                      " from user,attended where attended_user=user_id and attended_lecture=%s and user_activation=1",[id])
        students_attend=g.dbc.fetchall()
        session["students_attend"]=[i[0] for i in students_attend]
        # fetch all classrooms in institute
        g.dbc.execute("select classroom_id ,classroom_number from classroom where classroom_institute=%s",
                      [session["account"]["id"]])
        classrooms = g.dbc.fetchall()

        g.dbc.execute("select user_id, user_institute_id, user_first_name, user_last_name from user, enrolled_in"
                      " where user_id not in (select user_id from user, attended where "
                      "attended_user = user_id and attended_lecture=%s)"
                      "and  user_id = enrolled_in_user and enrolled_in_section=%s ", [id,session["section_id"]])
        students = g.dbc.fetchall()
        return jsonify({"classrooms": classrooms,"classroom_ins":classroom_ins, "students": students,"lecture":lecture,"students_attend":students_attend})
    except SQLError as error:
        print(error)
        return jsonify({"error": error})


@app.route('/lecture-add',methods=["GET","POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_add():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    if request.method == "GET":
        try:
            # fetch all classrooms in institute
            g.dbc.execute("select classroom_id ,classroom_number from classroom where classroom_institute=%s",
                          [session["account"]["id"]])
            classrooms = g.dbc.fetchall()


            g.dbc.execute("select user_id, user_institute_id, user_first_name, user_last_name from user, enrolled_in"
                          " where user_id = enrolled_in_user and enrolled_in_section=%s",[session["section_id"]])
            students=g.dbc.fetchall()
            return jsonify({"classrooms": classrooms,"students" : students})
        except SQLError as error:
            print(error)
            return jsonify({"error": error})
    elif request.method =="POST":
        try:
            start = request.form["start-time"]
            end = request.form["end-time"]
            day = request.form["day"]
            classroom = request.form["classroom"]

            if not (is_valid_time(start)):
                return redirect(url_for("section_details", id=session["section_id"],
                                        error="time_error"))

            if not (is_valid_time(end)):
                return redirect(url_for("section_details", id=session["section_id"],
                                        error="time_error"))

            g.dbc.execute("insert into lecture_record (lecture_record_section,lecture_record_classroom,"
                          "lecture_record_start,lecture_record_end,lecture_record_date) values"
                          "(%s,%s,%s,%s,%s)",[session["section_id"],classroom,start,end,day])
            g.db_connection.commit()

            return redirect(url_for("section_details", id=session["section_id"]))
        except SQLError as error:
            print(error)
            return redirect(url_for("section_details", id=session["section_id"], error="error"))


@app.route('/lecture-edit',methods=["POST"])
@restrict_access(access="private")
@database_access
def lecture_edit():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        if session["account"]["account_type"]=="institute":
            start = request.form["start-time"]
            end = request.form["end-time"]
            day = request.form["day"]
            classroom = request.form["classroom"]
            if not (is_valid_time(start)):
                return redirect(
                    url_for("section_details", id=session["section_id"],
                            error="time_error"))

            if not (is_valid_time(end)):
                return redirect(
                    url_for("section_details", id=session["section_id"],
                            error="time_error"))

            g.dbc.execute("update lecture_record set lecture_record_classroom=%s,lecture_record_start=%s,"
                          "lecture_record_end=%s, lecture_record_date=%s where "
                          " lecture_record_id=%s", [classroom, start, end, day, session["lecture_id"]])
            g.db_connection.commit()

        student=request.form.getlist("student-attend")

        students= [int(i)for i in student]

        for i in range(len(students)):
            g.dbc.execute("select * from attended where attended_user=%s and attended_lecture=%s"
                          ,[students[i],session["lecture_id"]])
            result=g.dbc.fetchall()
            if len(result) < 1 :
                g.dbc.execute("insert into attended(attended_user,attended_lecture) values (%s,%s)"
                              ,[students[i],session["lecture_id"]])
                g.db_connection.commit()

        for i in range(len(session["students_attend"])):
            if not(session["students_attend"][i] in students):
                g.dbc.execute("delete from attended where attended_user=%s and attended_lecture=%s"
                              ,[session["students_attend"][i],session["lecture_id"]])
                g.db_connection.commit()

        session.pop("lecture_id")
        session.pop("students_attend")
        return redirect(url_for("section_details", id=session["section_id"]))
    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", id=session["section_id"], error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(url_for("section_details", id=session["section_id"], error="error"))


@app.route('/lecture-delete',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def lecture_delete():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        g.dbc.execute("delete from lecture_record where lecture_record_id=%s"
                      , [session["lecture_id"]])
        g.db_connection.commit()

        session.pop("lecture_id")
        session.pop("students_attend")
        return redirect(url_for("section_details", id=session["section_id"]))
    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", id=session["section_id"], error="sql_error"))


@app.route('/student-details/<int:id>')
@restrict_access(access="private")
@database_access
def student_details(id):
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    session["student_id"]=id
    try:
        # fetch user information
        g.dbc.execute("select user_id, user_institute_id, user_first_name,user_last_name from user "
                      "where user_id=%s",[id])
        user=g.dbc.fetchall()

        # fetch attended lecture for user
        g.dbc.execute("select lecture_record_id, DATE_FORMAT(lecture_record_date, '%Y-%m-%d'),lecture_record_start"
                      ",lecture_record_end,lecture_record_counter,attended_counter "
                      "from lecture_record, attended where attended_user=%s and"
                      " lecture_record_id = attended_lecture and lecture_record_section =%s",
                      [id, session["section_id"]])
        lectures_attend=g.dbc.fetchall()
        # percentage of attendance
        student_pre=list()
        for i in range(len(lectures_attend)):
            student_pre.append("{0:.2f} %".format(get_student_attendance(lectures_attend[i][4],lectures_attend[i][5])))
        session["lectures_attend"] = [i[0] for i in lectures_attend]

        # fetch other lecturer
        g.dbc.execute("select lecture_record_id, DATE_FORMAT(lecture_record_date, '%Y-%m-%d'), lecture_record_start,"
                      " lecture_record_end from lecture_record where lecture_record_id not in "
                      "(select lecture_record_id from lecture_record, attended where attended_user=%s and "
                      "lecture_record_id = attended_lecture and lecture_record_section =%s)"
                      " and lecture_record_section =%s"
                      ,[id, session["section_id"],session["section_id"]])
        lectures=g.dbc.fetchall()
        return jsonify({"user": user, "lectures": lectures,"lectures_attend":lectures_attend,"student_pre":student_pre})
    except SQLError as error:
        print(error)
        return jsonify({"error": error})


@app.route('/student-add',methods=["GET","POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def student_add():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    if request.method == "GET":
        try:
            # fetch all user in institute
            g.dbc.execute("select user_id, user_institute_id,user_first_name, user_last_name "
                          "from user where user_id not in (select enrolled_in_user from enrolled_in "
                          "where enrolled_in_section=%s) and "
                          " user_account_type='student' and user_institute=%s and user_activation=1",[session["section_id"],session["account"]["id"]])
            users=g.dbc.fetchall()

            # fetch all lecture records for section
            g.dbc.execute("select lecture_record_id, DATE_FORMAT(lecture_record_date, '%Y-%m-%d'),lecture_record_start,lecture_record_end "
                          "from lecture_record where lecture_record_section=%s",[session["section_id"]])
            lectures=g.dbc.fetchall()
            return jsonify({"users": users, "lectures": lectures})
        except SQLError as error:
            print(error)
            return jsonify({"error": error})

    elif request.method == "POST":
        try:
            student=request.form["student"]
            lectures=request.form.getlist("lecture-attend")

            g.dbc.execute("insert into enrolled_in (enrolled_in_user, enrolled_in_section) values(%s,%s)"
                          ,[student,session["section_id"]])
            g.db_connection.commit()

            for lecture in lectures:
                g.dbc.execute("insert into attended(attended_user,attended_lecture) values(%s,%s)"
                              ,[student,lecture])
                g.db_connection.commit()

            return redirect(url_for("section_details", id=session["section_id"]))
        except SQLError as error:
            print(error)
            return redirect(
                url_for("section_details", id=session["section_id"], error="sql_error"))


@app.route('/student-edit',methods=["POST"])
@restrict_access(access="private")
@database_access
def student_edit():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        student = request.form["student"]
        lecture = request.form.getlist("lecture-attend")

        lectures = [int(i) for i in lecture]

        for i in range(len(lectures)):
            g.dbc.execute("select * from attended where attended_user=%s and attended_lecture=%s"
                          , [session["student_id"],lectures[i]])
            result = g.dbc.fetchall()
            if len(result) < 1:
                g.dbc.execute("insert into attended(attended_user,attended_lecture) values (%s,%s)"
                              , [session["student_id"],lectures[i]])

        for i in range(len(session["lectures_attend"])):
            if not (session["lectures_attend"][i] in lectures):
                g.dbc.execute("delete from attended where attended_user=%s and attended_lecture=%s"
                              , [session["student_id"],session["lectures_attend"][i]])

        g.db_connection.commit()
        session.pop("student_id")
        session.pop("lectures_attend")
        return redirect(url_for("section_details", id=session["section_id"]))

    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", id=session["section_id"], error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(url_for("section_details", id=session["section_id"], error="error"))


@app.route('/student-delete',methods=["post"])
@restrict_access(access="private", account_type="institute")
@database_access
def student_delete():
    if not (session["section_id"]):
        return redirect(url_for('dashboard', value_error="section_found"))

    try:
        g.dbc.execute("delete from enrolled_in where enrolled_in_user=%s and enrolled_in_section=%s"
                      ,[session["student_id"],session["section_id"]])

        g.dbc.execute("delete from attended where attended_lecture in (select attended_lecture from attended, "
                      "lecture_record where attended_lecture=lecture_record_id and lecture_record_section=%s)"
                      " and attended_user=%s",[session["section_id"],session["student_id"]])

        g.db_connection.commit()

        session.pop("student_id")
        session.pop("lectures_attend")
        return redirect(url_for("section_details", id=session["section_id"]))

    except SQLError as error:
        print(error)
        return redirect(url_for("section_details", id=session["section_id"], error="sql_error"))
    except Exception as e:
        print(e)
        return redirect(url_for("section_details", id=session["section_id"], error="error"))


@app.route('/user-details/<int:id>')
@restrict_access(access="private",account_type="institute")
@database_access
def user_details(id):
    session["user_id"] = id
    try:
        # fetch user information
        g.dbc.execute("select user_id, user_institute_id, user_first_name, user_last_name ,"
                      " user_email,user_account_type, user_activation from user "
                      "where user_id=%s and user_institute=%s", [id, session["account"]["id"]])
        user = g.dbc.fetchall()

        # get the user images
        images=list()
        g.dbc.execute("select user_images_paths_path from user_image_paths where user_images_paths_user=%s",[id])
        result=g.dbc.fetchall()
        for file in result:
            images.append(get_image_data_url(os.path.join(
                    app.config['UPLOAD_FOLDER'], file[0]+".png")))

        locale_file_name = "arabic"
        if "locale" in request.cookies:
            locale_file_name = request.cookies["locale"]
        with app.open_resource("static/locale/{}.json".format(locale_file_name)) as f:
            locale = json.load(f)
        return jsonify({"user": user,"types":locale["user-type"],"activation":locale["activation-type"],"images":images})
    except SQLError as error:
        print(error)
        return jsonify({"error": error})


@app.route('/delete-active-user',methods=["POST"])
@restrict_access(access="private", account_type="institute")
@database_access
def delete_active_user():
    id=session["user_id"]
    try:
        g.dbc.execute("delete from user where user_id =%s and user_institute=%s", [id, session["account"]["id"]])
        g.db_connection.commit()
        if "user_id" in session:
            session.pop("user_id",None)
        return redirect(url_for('dashboard'))
    except SQLError as error:
        print(error)
        return redirect(url_for('dashboard', error="sql error"))


@app.route('/class-log')
@restrict_access(access="private", account_type="institute")
@database_access
def class_log():
    id=session["classroom_id"]
    log=""
    students=""
    student_attend=""
    time=""
    try:
        # get the log file
        g.dbc.execute("select classroom_log_path from classroom where classroom_id=%s ",[id])
        file=g.dbc.fetchall()[0][0]
        if file is not None and file != "NULL" and os.path.isfile(file):
            with open(file,"r") as file:
                log=file.read()
        else:
            log = "Log file not found!"
        # get the attended students
        student_attend=list()
        g.dbc.execute("select lecture_record_id , lecture_record_counter, lecture_record_end from lecture_record where lecture_record_active=1")
        result=g.dbc.fetchall()
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        time = datetime.strptime(result[0][2], "%H:%M") - datetime.strptime(current_time, "%H:%M")
        g.dbc.execute("select user_institute_id, user_first_name, user_last_name,attended_counter "
                      "from user, attended where attended_lecture=%s and user_id=attended_user ",[result[0][0]])
        students=g.dbc.fetchall()
        for i in range(len(students)):
            student_attend.append("{0:.2f} %".format(get_student_attendance(result[0][1],students[i][3])))
        
    except SQLError as error:
        print(error)
        # return jsonify({"error":"sql error"})
    except Exception as e:
        print(e)
        # return jsonify({"error": "error"})
        
    return jsonify({"log":log,"students":students,"student_attend":student_attend,"time":str(time)})


def get_student_attendance(lecture_counter,student_counter):
    try:
        return (student_counter/lecture_counter)*100
    except Exception as e:
        print(e)
        return 0.00











if __name__ == '__main__':
    app.debug = True
    app.run()

# def main():
#     app.debug = True
#     app.run()