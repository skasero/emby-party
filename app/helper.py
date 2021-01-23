import app
import datetime
import random
import platform
import requests
import json
import string
import threading
import time
from app import INTERVAL, app
from app import db
from app import functions
from app.models import Session
from app.models import User
from app.models import Room
from flask_login import current_user


## Broken
# def addAllUsers():
#     responses = getSessionJson()
#     printJsonResponce(responses)
#     for response in responses:
#         user = db.session.query(User).filter_by(username=response['User']['Name'].lower()).first()
#         ## If the user cannot be found in the database, add it
#         if(not user):
#             newuser = User(emby_id=response['User']['Id'], username=response['User']['Name'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
#             db.session.add(newuser)
#             db.session.commit()

def getUserJson():
    url = '{0}/Users'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'applicaton/json',
        'X-Emby-Token': app.config['SECRET_KEY'],
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Client': platform.system()
    }
    response = requests.get(url, headers=headers)
    response_json = response.json()

    return response_json

def getSessionJson():
    url = '{0}/Sessions'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'applicaton/json',
        'X-Emby-Token': app.config['SECRET_KEY'],
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Client': platform.system()
    }
    response = requests.get(url, headers=headers)
    response_json = response.json()

    return response_json

def getSessionList():
    sessions = getSessionJson()
    embySessionList = []
    for session in sessions:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=session['Id']).first()
            
            ## Checking if the emby_session isn't None
            if(emby_session):
                embySessionList.append(emby_session)

        except KeyError:
            continue
    
    return embySessionList

def printJsonResponce(responce):
    print(json.dumps(responce,indent=3))

def check_sync(session_ticks, room_ticks):
    drift = (session_ticks/10000000) - (room_ticks/10000000)
    return drift