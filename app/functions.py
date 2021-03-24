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
from app.helper import *
from app.commands import *

## TODO
## Add ability to join back in session after left it they join the same video
## Move functions to different file


def initRun():
    allSessions = Session.query.all()
    for session in allSessions:
        session.syncing = True
        session.loading = False
    
    # allRooms = Room.query.all()
    # for room in allRooms:
    #     emptyRoom(room)
    db.session.commit()   

def check_password(username, password):
    url = '{0}/Users/Authenticatebyname'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(), 
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': ''.join(random.choices(string.ascii_uppercase + string.digits, k = 24)),
        'X-Emby-Device-Name': 'Emby Sync'
    }
    data = { 'Username': username, 'Pw': password }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        response_json = response.json()
        update_or_create_account(response_json)
        return True
    else:
        print(response.text, flush=True)
        return False

def update_or_create_account(response):
    user = db.session.query(User).filter_by(username=response['User']['Name'].lower()).first()
    if user:
        user.device_id = response['SessionInfo']['DeviceId']
        user.access_key = response['AccessToken']
        db.session.commit()
        update_or_create_sessions()
        return True
    else:
        newuser = User(emby_id=response['User']['Id'], username=response['User']['Name'].lower(), access_key=response['AccessToken'], device_id=response['SessionInfo']['DeviceId'])
        db.session.add(newuser)
        db.session.commit()
        return True

def end_session():
    for z in current_user.sessions:
        set_dead(z.session_id)
        db.session.commit()
        session_cleanup()

    url = '{0}/Sessions/Logout'.format(app.config['EMBY_SERVER'])
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Emby-Client': platform.system(),
        'X-Emby-Client-Version': '0.1',
        'X-Emby-Device-Id': current_user.device_id,
        'X-Emby-Device-Name': 'Emby Sync'
        # 'X-Emby-Token': current_user.access_key
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return True
    else:
        print(response.text, flush=True)
        return False

def update_or_create_sessions():
    ## Just for the Emby Sync user aka the bot
    emby_session = db.session.query(Session).filter_by(device_id='session-sync').all()
    for z in emby_session:
        try:
            set_room(app.config['DEFAULT_ROOM'], z.session_id)
        except KeyError:
            continue

    response_json = getSessionJson()

    newlastTimeUpdatedAt = datetime.datetime.now()
    active_users = []
    for z in response_json:
        try:
            emby_session = db.session.query(Session).filter_by(session_id=z['Id']).first()
            date_time_obj = datetime.datetime.fromisoformat(z['LastActivityDate'][:-2])
            ip_obj = z['RemoteEndPoint']
            # if stale_calc(date_time_obj, 300):
            #     continue
            if emby_session:
                emby_session.timestamp = date_time_obj
                emby_session.ip_address = ip_obj
                if(emby_session.loading == False):
                    ## Do nothing as nothing has changed in the user
                    if('NowPlayingItem' in z):
                        if(emby_session.playing == True and 
                            emby_session.item_id == int(z['NowPlayingItem']['Id']) and 
                            emby_session.ticks == z['PlayState']['PositionTicks'] and 
                            emby_session.is_paused == z['PlayState']['IsPaused']):
                            pass
                        else:
                            if(emby_session.room_id):
                                room = db.session.query(Room).filter_by(id=emby_session.room_id).first()
                                if(room.playing == False):
                                    print('Setting room with brand new play')
                                    room.playing = True
                                    room.item_id = z['NowPlayingItem']['Id']
                                    room.ticks = z['PlayState']['PositionTicks']
                                    room.is_paused = z['PlayState']['IsPaused']
                                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                                    # emby_session.initial = False
                                    # db.session.commit()

                            emby_session.playing = True
                            emby_session.item_id = z['NowPlayingItem']['Id']
                            emby_session.ticks = z['PlayState']['PositionTicks']
                            emby_session.is_paused = z['PlayState']['IsPaused']
                            # if(emby_session.initial == False):
                            emby_session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    else:
                        ## Do nothing as nothing has changed in the user
                        if(emby_session.playing == False and 
                            emby_session.item_id == None and 
                            emby_session.ticks == None and 
                            emby_session.is_paused == z['PlayState']['IsPaused']):
                            pass
                        else:
                            emby_session.playing = False
                            emby_session.item_id = None
                            emby_session.ticks = None
                            emby_session.is_paused = z['PlayState']['IsPaused']
                            # if(emby_session.initial == False):
                            emby_session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                else:
                    print('happened')
            else:
                if z['DeviceId'] != 'session-sync':
                    print("new session user")
                    newsession = Session(user_id=z['UserId'], session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)
                else:
                    newsession = Session(session_id=z['Id'], device_name=z['DeviceName'], timestamp=date_time_obj, client_name=z['Client'], device_id=z['DeviceId'], ip_address=ip_obj)
                    db.session.add(newsession)

            db.session.commit()
            active_users.append(z['Id'])

        except KeyError:
            print(KeyError)
            continue
    
    return active_users

def set_leader(room_name, emby_session_id):
    print("set_leader")
    emby_session = db.session.query(Session).filter_by(room=room_name, leader=True).first()
    if emby_session:
        emby_session.leader = False
        db.session.commit()
        emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
        emby_session.room = room_name
        emby_session.leader = True
        db.session.commit()
    return True

def emptyRoom(room):
    room.ticks = 0
    room.item_id = None
    room.is_paused = False
    room.playing = False
    db.session.commit()

def create_room(room_name):
    print(f'Creating new room: {room_name}')
    current_time = datetime.datetime.now()
    new_room = Room(roomname=room_name,lastTimeUpdatedAt=current_time)
    db.session.add(new_room)
    db.session.commit()

def set_room(room_name, emby_session_id):
    room = db.session.query(Room).filter_by(roomname=room_name).first()
    if(not room):
        create_room(room_name)
    emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
    room = db.session.query(Room).filter_by(roomname=room_name).first()
    emby_session.room_id = room.id
    emby_session.syncing = True
    emby_session.loading = False
    emby_session.initial = True
    emby_session.lastTimeUpdatedAt = datetime.datetime.min ## Oldest date possible
    db.session.commit()
    
    ## For when a new person joins that isn't the bot
    if(emby_session.device_id != 'session-sync'):
        # sendCommand(emby_session.session_id, "Message")
        pass

    return True

def stale_check(in_sesh):
    if (in_sesh.is_stale == False) and (stale_calc(in_sesh.timestamp, 300)):
        in_sesh.is_stale = True
        db.session.commit()
    if (in_sesh.is_stale == True) and not (stale_calc(in_sesh.timestamp, 120)):
        in_sesh.is_stale = False
        db.session.commit()
    if (in_sesh.is_stale == True) and (stale_calc(in_sesh.timestamp, 600)):
        set_dead(in_sesh.session_id)
        session_cleanup()
    return True

def stale_calc(time, limit):
    staleTime = datetime.datetime.utcnow() - time
    staleTime = abs(staleTime.total_seconds())
    if staleTime > limit:
        return True
    else:
        return False

def set_dead(emby_session_id):
    emby_session = db.session.query(Session).filter_by(session_id=emby_session_id).first()
    emby_session.is_dead = True
    db.session.commit()
    return True

def session_cleanup():
    Session.query.filter(Session.is_dead==True).delete()
    db.session.commit()

def updateRoom(room, active_room_sessions) -> bool:
    # print(f'Updating information for room: {room.roomname}')

    ## Commented as I have to deal with a situation where the room is empty, but maybe the user hasn't had syncing set to true
    # if(len(active_room_sessions) == 0):
    #     # print(f'{room.roomname} is empty')
    #     emptyRoom(room)
    #     return False

    newlastTimeUpdatedAt = datetime.datetime.now()
    checkForAnyUserPlaying = False
    for session in active_room_sessions:
        # print(f'room:    {room.lastTimeUpdatedAt}')
        # print(f'session: {session.lastTimeUpdatedAt}')
        if(session.syncing == True):
            ## This is to set a session to no longer get synced as it has left the video currently playing
            if((room.playing == True and session.playing == False) and room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt):
                print('Session has left the sync')
                session.syncing = False
                session.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (room.is_paused == False and session.is_paused == True) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                print('Pausing room')
                room.is_paused = True
                room.ticks = session.ticks
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (room.is_paused == True and session.is_paused == False) and (room.item_id == session.item_id) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                print('Resuming room')
                room.is_paused = False
                room.ticks = session.ticks
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
            elif((room.playing == True and session.playing == True) and (session.ticks != 0 and room.item_id == session.item_id) and (room.lastTimeUpdatedAt <= session.lastTimeUpdatedAt)):
                sync_drift = check_sync(session.ticks, room.ticks)
                # print(f'sync: {sync_drift}')
                localTime = session.lastTimeUpdatedAt - datetime.timedelta(seconds=sync_drift)
                # print(f'session update: {session.lastTimeUpdatedAt}')
                # print(f'local: {localTime}')
                # print(f'room update: {room.lastTimeUpdatedAt}')
                # print(f'server: {serverTime}')
                timeDifference = localTime - room.lastTimeUpdatedAt
                # print(f'diff: {timeDifference.total_seconds()}')
                if(abs(timeDifference.total_seconds()) >= 10):
                    print('Time difference, updating server and pausing room')
                    room.is_paused = True
                    room.ticks = session.ticks
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    
        else:
            ## This is for when a session start playing a different video from the room, this will update the room
            if(room.playing == True and session.playing == True and room.item_id != session.item_id):
                print('A user has started a different video while another one was playing')
                room.item_id = session.item_id
                room.ticks = session.ticks
                room.is_paused = session.is_paused
                room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                session.syncing = True
                session.lastTimeUpdatedAt = newlastTimeUpdatedAt

        ## This is used to see if any user is actually currently watching something, else set the
        ## the room state to nothing
        if(session.playing == True and checkForAnyUserPlaying == False):
            checkForAnyUserPlaying = True

        db.session.commit()

    ## No user is playing anything, set room state to nothing
    if(not checkForAnyUserPlaying and room.playing != False):
        print('No user was playing anything, setting room to not playing')
        room.playing = False
        room.item_id = None
        room.ticks = None
        room.is_paused = True
        for session in active_room_sessions:
            session.syncing = True
            session.loading = False
        room.lastTimeUpdatedAt = newlastTimeUpdatedAt
        
    db.session.commit()
    return True

def sync_cycle():
    print('==========================================================')
    start = time.time()
    active_users = update_or_create_sessions()
    full_session_list = Session.query.all()
    ## This will only get the users that are actually connected to the Emby server
    active_session_list = [session for session in full_session_list if(session.session_id in active_users)]
    
    rooms = Room.query.all()
    for room in rooms:
        # sessions = Session.query.filter(Session.room_id == room.id, Session.device_id != 'session-sync').all()
        sessions = [session for session in active_session_list if(session.room_id == room.id and session.device_id != 'session-sync')]
        
        ## This means that the room is completely empty, skip it
        if(updateRoom(room,sessions) == 0):
            continue
        print(f'Room is_paused: {room.is_paused}')
        print(f'Room ticks: {room.ticks}')
        print(f'Room item_id: {room.item_id}')
        print(f'Room playing: {room.playing}')
        print(f'Room lastTimeUpdatedAt: {room.lastTimeUpdatedAt}')

        newlastTimeUpdatedAt = datetime.datetime.now()
        for session in sessions:
            if(session.syncing == True):
                # print(f'{room.is_paused} - {room.playing}')
                # print(f'{session.is_paused} - {session.playing}')
                ## If the room is currently has a video playing and the user doesn't
                ## Or if the room and user doesn't have the same video playing
                if((room.playing == True) and (session.playing == False or room.item_id != session.item_id) and (session.ticks != 0)):
                    print("Session is not playing anything, starting session video")
                    room.is_paused = True
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.syncing = False
                    session.is_paused = True
                    session.initial = False
                    db.session.commit()
                    # sendCommand(session.session_id,'Pause')
                    sendRoomCommand(room,sessions,'Pause')
                    app.apscheduler.add_job(func=sync, trigger='date', args=[room.ticks,room.item_id,session.session_id], id="Sync "+session.session_id)    
                ## 
                if((room.playing == True and session.playing == True) and (room.is_paused == True and session.is_paused == False)):
                    print("Pausing all followers")
                    # room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.syncing = False
                    db.session.commit()
                    app.apscheduler.add_job(func=issuePause, trigger='date', args=[session.session_id], id="Command "+session.session_id)    
                    # sendCommand(session.session_id,'Pause')
                ##
                if((room.playing == True and session.playing == True) and (room.is_paused == False and session.is_paused == True)):
                    print("Resuming all followers")
                    room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                    session.syncing = False
                    db.session.commit()
                    app.apscheduler.add_job(func=issueResume, trigger='date', args=[session.session_id], id="Command "+session.session_id)    
                    # sendCommand(session.session_id,'Unpause')
                ##
                if((room.playing == True and session.playing == True) and (room.item_id == session.item_id and session.ticks != 0)):
                    sync_drift = check_sync(session.ticks, room.ticks)
                    localTime = session.lastTimeUpdatedAt - datetime.timedelta(seconds=sync_drift)
                    timeDifference = localTime - room.lastTimeUpdatedAt
                    if(abs(timeDifference.total_seconds()) >= 10):
                        print('Follower out of sync, syncing with room')
                        room.is_paused = True
                        room.lastTimeUpdatedAt = newlastTimeUpdatedAt
                        session.lastTimeUpdatedAt = newlastTimeUpdatedAt
                        session.syncing = False
                        session.is_paused = True
                        session.loading = True
                        session.initial = False
                        db.session.commit()
                        sendCommand(session.session_id,'Pause')
                        app.apscheduler.add_job(func=syncTicks, trigger='date', args=[room.ticks,room.lastTimeUpdatedAt,session.session_id], id="Sync "+session.session_id)     
    
    end = time.time()
    # print(f'Round trip: {end - start}')
    
def sync(room_ticks, room_item, sessionId):
    target = room_ticks + int(INTERVAL*10000000) # Load x seconds ahead to give user time to buffer
    setPlaytime(sessionId, target, room_item)

    ## This is a do-while loop
    while(True):
        sendCommand(sessionId, "Pause")
        with app.app_context():
            session = db.session.query(Session).filter_by(session_id=sessionId).first()
            print('test')
            if(session.ticks != None and (session.ticks >= target or session.ticks == 0) and (session.is_paused == True and session.item_id == room_item)):
                session.syncing = True
                print('Session is now synced with server')
                db.session.commit()
                break

def syncTicks(room_ticks, room_lastTimeUpdatedAt, sessionId):
    target = room_ticks + int(INTERVAL*10000000) # Load x seconds ahead to give user time to buffer
    setTickPosition(sessionId, target)
    targetLower = target - 20000 # I used 20000 ticks as this value is equal to .002 of a second. 
    targetUpper = target + 20000 # I used 20000 ticks as this value is equal to .002 of a second. 
    
    with app.app_context():
        session = db.session.query(Session).filter_by(session_id=sessionId).first()
        session.loading = False
        db.session.commit()
    # time.sleep(INTERVAL/2)

    ## This is a do-while loop
    while(True):
        with app.app_context():
            session = db.session.query(Session).filter_by(session_id=sessionId).first()
            # if(session.ticks != None):
            #     print('ticks are not none')
            # if(session.ticks >= targetLower and session.ticks <= targetUpper):
            #     print('ticks are target')
            # if session.ticks == 0:
            #     print('ticks are 0')
            # if(session.lastTimeUpdatedAt > room_lastTimeUpdatedAt):
            #     print('session is updated more than room')

            if(session.ticks != None and ((session.ticks >= targetLower and session.ticks <= targetUpper) or session.ticks == 0) and session.lastTimeUpdatedAt > room_lastTimeUpdatedAt):
                session.syncing = True
                db.session.commit()
                print('Session is now synced with server')
                break
    
def get_room_leader(room):
    leader_session = db.session.query(Session).filter_by(room=room, leader=True).first()
    if leader_session and leader_session.device_name != 'Emby Connect':
        return "  --  Current leader is "
    else:
        return ""

def get_room_name(session):
    room = db.session.query(Room).filter_by(id=session.room_id).first()
    if(room):
        return f' -- Synced to {room.roomname}'
    return ' -- Not Synced'
