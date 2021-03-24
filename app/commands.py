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


def sendRoomCommand(room, active_room_sessions, command):
    print(f'Issuing command: {command} for room: {room.roomname}')
    newlastTimeUpdatedAt = room.lastTimeUpdatedAt
    for session in active_room_sessions:
        sendCommand(session.session_id,command)
        session.lastTimeUpdatedAt = newlastTimeUpdatedAt
    db.session.commit()

def issuePause(sessionId):
    sendCommand(sessionId,'Pause')

    while(True):
        with app.app_context():
            session = db.session.query(Session).filter_by(session_id=sessionId).first()
            if(session.is_paused == True):
                session.syncing = True
                db.session.commit()
                break

def issueResume(sessionId):
    sendCommand(sessionId,'Unpause')

    while(True):
        with app.app_context():
            session = db.session.query(Session).filter_by(session_id=sessionId).first()
            if(session.is_paused == False):
                session.syncing = True
                db.session.commit()
                break

def setTickPosition(sessionId, ticks):
    url = '{0}/Sessions/{1}/Playing/Seek'.format(app.config['EMBY_SERVER'], sessionId)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'SeekPositionTicks': ticks
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

def setPlaytime(sessionId, ticks, item_id):
    url = '{0}/Sessions/{1}/Playing'.format(app.config['EMBY_SERVER'], sessionId)
    print(url)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'ItemIds': item_id,
        'StartPositionTicks': ticks
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

def sendCommand(sessionId, command):
    url = '{0}/Sessions/{1}/Playing/{2}'.format(app.config['EMBY_SERVER'], sessionId, command)

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }

    response = requests.post(url, headers=headers)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)

def sendMessage(sessionId, message = 'Click "Got It" to Watch Together'):
    url = '{0}/Sessions/{1}/Message'.format(app.config['EMBY_SERVER'], sessionId)
        
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': 'session-sync',
        'X-Emby-Device-Name': 'Emby Sync',
        'X-Emby-Token': app.config['SECRET_KEY']
    }
    params = {
        'Text': message,
        'Header': '&emsp;&emsp;Emby - Party&emsp;&emsp;'
    }
    response = requests.post(url, headers=headers,params=params)
    if response.status_code == 204:
        return 0
    else:
        print(response.text, flush=True)
        print(response.status_code, flush=True)