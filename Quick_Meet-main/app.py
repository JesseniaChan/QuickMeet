from __future__ import print_function

import time, schedule

from flask import Flask, render_template, redirect, url_for, session, request as flask_request, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from google_auth_oauthlib.flow import InstalledAppFlow
import secrets
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.apps import meet_v2

from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import openai
import base64


openai.api_key = 'secret key'

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

db = SQLAlchemy()
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///meeting.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

global response
meeting = None
user_name = None
description_info = None
creation_time = None

#List
room_names = []
created_by = []
descriptions = []
links = []
time_event_created = []
script = []
pdf_list = []
study_guide_list = []

# OAuth 2.0 configuration
SCOPES = ['https://www.googleapis.com/auth/meetings.space.created']
CLIENT_SECRETS_FILE = 'credentials.json'
REDIRECT_URI = 'http://localhost:5000/oauth_callback'

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meeting_name = db.Column(db.String(250), nullable=True)
    creator_name = db.Column(db.String(250), nullable=True)
    description = db.Column(db.String(2500), nullable=True)
    url = db.Column(db.String(2500), nullable=True)
    # tag1 = db.Column(db.String(250), nullable=True)
    # tag2 = db.Column(db.String(250), nullable=True)
    # tag3 = db.Column(db.String(250), nullable=True)
    # tag4 = db.Column(db.String(250), nullable=True)
    # tag5 = db.Column(db.String(250), nullable=True)
    time_created = db.Column(db.Integer, nullable =True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_meeting', methods=['GET', 'POST'])
def new_meeting():
    if flask_request.method == 'GET':
        return render_template('new_meeting.html')
    elif flask_request.method == "POST":
        if flask_request.form['Create_Meeting'] == "Create Meeting":
            meeting = flask_request.form.get("meeting_name")
            user_name = flask_request.form.get("creator_name")
            description_info = flask_request.form.get("description")
            creation_time = time.time()

            session['meeting'] = meeting
            # session['user_name'] = user_name
            # session['description_info'] = description_info

            creds = None

            # Create OAuth 2.0 flow
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )

            #Create Meeting Room
            creds = flow.run_local_server(port=0)
            client = meet_v2.SpacesServiceClient(credentials=creds)
            request = meet_v2.CreateSpaceRequest()
            response = client.create_space(request=request)

            session['flag'] = False

            return redirect(url_for('space_created', uri=response.meeting_uri, meeting=meeting, user_name=user_name, description=description_info, time = creation_time))

@app.route('/space_created')
def space_created():
    uri = flask_request.args.get('uri')
    meeting = flask_request.args.get('meeting')
    user_name = flask_request.args.get('user_name')
    description_info = flask_request.args.get('description')
    time = flask_request.args.get('time')
    flag = session.get('flag')
    if(not flag):
        session['flag'] = True
        update(meeting, user_name, description_info, uri, time_created = time)
    return render_template('space_created.html', meeting_uri = uri, meeting = meeting, user_name = user_name, description = description_info)

@app.route('/find_space')
def find_space():    
    update_list()
    # study_guide_list.clear()
    # for a in room_names:
    #     study_guide = generate_study_guide(a)
    #     study_guide_list.append(study_guide)
    # pdf_list = generate_study_guide_pdf(study_guide_list)
    return render_template('find_space.html', room_names = room_names, created_by = created_by, descriptions = descriptions, links = links, enumerate=enumerate)

text_content = ""

@app.route('/generate_pdf')
def generate_pdf():
    global text_content
    meeting = session.get('meeting')
    if meeting:
        # Sample text content
        # generate_study_guide(meeting)
        study_guide = generate_study_guide(meeting)

        text_content = study_guide

        # Convert text to PDF
        pdf_data = text_to_pdf(text_content)
        
        # Save PDF to a temporary file
        temp_pdf = BytesIO()
        temp_pdf.write(pdf_data)
        temp_pdf.seek(0)

        return send_file(temp_pdf, mimetype='application/pdf')
    else:
        # Generate a default PDF when there's no meeting content
        default_text = text_content
        default_pdf_data = text_to_pdf(default_text)
        
        # Save default PDF to a temporary file
        temp_pdf = BytesIO()
        temp_pdf.write(default_pdf_data)
        temp_pdf.seek(0)

        return send_file(temp_pdf, mimetype='application/pdf')

def text_to_pdf(text_content):
     # Create a buffer to store PDF data
    pdf_buffer = BytesIO()

    # Create a canvas
    c = canvas.Canvas(pdf_buffer, pagesize=letter)

    # Set font and font size
    c.setFont("Helvetica", 12)

    # Set initial y position
    y = 750

    # Split the data into paragraphs and write each paragraph to the PDF
    paragraphs = text_content.split('\n\n')
    for paragraph in paragraphs:
        lines = paragraph.split('\n')
        for line in lines:
            # Check if the line exceeds the remaining space on the current page
            if y <= 50:
                # If the remaining space is not enough for another line, create a new page
                c.showPage()
                c.setFont("Helvetica", 12)  # Reset font and font size for the new page
                y = 750  # Reset y position for the new page
            # Split long lines into smaller chunks to fit the page width
            words = line.split()
            current_line = ""
            for word in words:
                # Check if adding the current word exceeds the page width
                if c.stringWidth(current_line + " " + word) > 500:  # Adjust the width as needed
                    # If it exceeds, draw the current line and start a new line
                    c.drawString(100, y, current_line)
                    y -= 15  # Adjust vertical position for the next line
                    current_line = word
                else:
                    # If it doesn't exceed, add the word to the current line
                    if current_line:
                        current_line += " "
                    current_line += word
            # Draw the remaining part of the line
            c.drawString(100, y, current_line)
            y -= 15  # Adjust vertical position for the next line

        y -= 20  # Adjust vertical position for the next paragraph

    # Save the PDF
    c.save()

    # Get PDF data
    pdf_data = pdf_buffer.getvalue()

    # Close buffer
    pdf_buffer.close()
    
    return pdf_data


def generate_study_guide(user_input):
    prompt = f"Please give me study guide with practice problems for {user_input} and add an overview of key concepts."

    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct", 
        prompt=prompt,
        max_tokens=1000,
        temperature=0.7
    )

    study_guide = response.choices[0].text.strip()
    return study_guide

    # guide = generate_study_guide(meeting)
# ANYTHING YOU DO REGARDING DATABASE MANIPULATION MUST HAPPEN UNDER with app.app_context():
with app.app_context():
    def update_list():
        room_names.clear()
        created_by.clear()
        descriptions.clear()
        links.clear()
        # Creates the database if they don't exist, this creates a database under the folder name instance called meeting.db
        db.create_all()

        #This creates a variable named the_menu that has all the data from Meeting
        data_read = db.session.query(Meeting).all()

        # Print the data
        for each_item in data_read:
            room_names.append(each_item.meeting_name)
            created_by.append(each_item.creator_name)
            descriptions.append(each_item.description)
            links.append(each_item.url)
            time_event_created.append(each_item.time_created)
        
        periodic_task()

    def update(meeting, user_name, description_info, uri, time_created):
        # This is the data that will be stored in the SQLAlchemy Database
        data = Meeting(meeting_name=meeting, creator_name=user_name, description=description_info, url = uri, time_created = time_created)
        # Add data to the database session
        db.session.add(data)

        # Commit the session to update the database
        db.session.commit()

def periodic_task():
    sizeOf = len(room_names)
    purge_these_times = []
    for i in range(0, sizeOf):
        if time_event_created[i] + (60*60) < time.time():
            del room_names[i]
            del created_by[i]
            del descriptions[i]
            del links[i]
            del time_event_created[i]
            with app.app_context():
                data_read = db.session.query(Meeting).all()
                for each_item in data_read:
                    if each_item.time_created + (60 * 60) < time.time():
                        db.session.delete(each_item)
                        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
