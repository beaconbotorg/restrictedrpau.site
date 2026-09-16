import os, sqlite3, secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, send_from_directory
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'events.db')

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv('FLASK_SECRET_KEY') or os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('COOKIE_SECURE', '0').lower() in ('1', 'true', 'yes')
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_NAME'] = 'restrictedrp_session'

DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID', '')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:3000/auth/discord/callback')
EVENT_MANAGER_ROLE_IDS = {x.strip() for x in os.getenv('EVENT_MANAGER_ROLE_IDS', '').split(',') if x.strip()}
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'Community',
            department TEXT DEFAULT 'General',
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            location TEXT DEFAULT '',
            postal TEXT DEFAULT '',
            capacity INTEGER DEFAULT 0,
            host TEXT DEFAULT '',
            featured INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS rsvps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(event_id, user_id),
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
        )''')


init_db()


def site_file(filename):
    return send_from_directory(BASE_DIR, filename)


@app.route('/')
def home():
    return site_file('index.html')


@app.route('/<path:filename>')
def website_files(filename):
    # Events gets its own Flask page; everything else is the original website file.
    if filename == 'events.html':
        return render_template('events.html')
    if filename == 'staff-events.html':
        return render_template('staff-events.html')
    full = os.path.join(BASE_DIR, filename)
    if os.path.isfile(full):
        return send_from_directory(BASE_DIR, filename)
    return ('Not Found', 404)


@app.route('/events')
def events_page():
    return render_template('events.html')


@app.route('/staff/events')
def staff_events_page():
    if not is_event_manager():
        return redirect('/events?staff_required=1')
    return render_template('staff-events.html')


def is_event_manager():
    if DEV_MODE and session.get('dev_user'):
        return True
    user = session.get('discord_user')
    roles = set(session.get('discord_roles', []))
    return bool(user and EVENT_MANAGER_ROLE_IDS and roles.intersection(EVENT_MANAGER_ROLE_IDS))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('discord_user'):
            return jsonify({'error': 'Discord login required'}), 401
        return fn(*args, **kwargs)
    return wrapper


def manager_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_event_manager():
            return jsonify({'error': 'You do not have an event-manager Discord role.'}), 403
        return fn(*args, **kwargs)
    return wrapper


@app.route('/auth/discord')
def discord_login():
    if not DISCORD_CLIENT_ID:
        return 'Discord OAuth is not configured. Fill in .env first.', 500
    state = secrets.token_urlsafe(48)
    # Store OAuth state server-side so the callback does not depend on the
    # browser returning Flask's session cookie after leaving for Discord.
    created = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with db() as conn:
        conn.execute('DELETE FROM oauth_states WHERE created_at < ?', ((datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec='seconds'),))
        conn.execute('INSERT INTO oauth_states(state, created_at) VALUES(?, ?)', (state, created))
    params = {
        'client_id': DISCORD_CLIENT_ID,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify guilds.members.read',
        'state': state,
    }
    return redirect('https://discord.com/oauth2/authorize?' + urlencode(params))


@app.route('/auth/discord/callback')
def discord_callback():
    state = request.args.get('state', '')
    if not state:
        return 'Invalid OAuth state.', 400
    # Validate and consume the one-time state from the server-side store.
    with db() as conn:
        row = conn.execute('SELECT state, created_at FROM oauth_states WHERE state=?', (state,)).fetchone()
        if row:
            conn.execute('DELETE FROM oauth_states WHERE state=?', (state,))
    if not row:
        return 'Invalid or expired OAuth state. Please start Discord login again.', 400
    code = request.args.get('code')
    if not code:
        return 'Discord authorization was cancelled.', 400
    token = requests.post('https://discord.com/api/oauth2/token', data={
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI,
    }, timeout=10)
    if token.status_code != 200:
        return 'Discord token exchange failed.', 502
    access_token = token.json().get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    me = requests.get('https://discord.com/api/users/@me', headers=headers, timeout=10)
    if me.status_code != 200:
        return 'Could not read your Discord account.', 502
    user = me.json()
    roles = []
    if DISCORD_GUILD_ID:
        member = requests.get(f'https://discord.com/api/users/@me/guilds/{DISCORD_GUILD_ID}/member', headers=headers, timeout=10)
        if member.status_code == 200:
            roles = member.json().get('roles', [])
    session['discord_user'] = {
        'id': user['id'],
        'username': user.get('global_name') or user.get('username') or 'Discord User',
        'avatar': user.get('avatar'),
    }
    session['discord_roles'] = roles
    return redirect('/events')


@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect('/events')


@app.route('/api/me')
def api_me():
    user = session.get('discord_user')
    return jsonify({
        'logged_in': bool(user),
        'user': user,
        'event_manager': is_event_manager(),
        'configured': bool(DISCORD_CLIENT_ID and DISCORD_GUILD_ID and EVENT_MANAGER_ROLE_IDS),
    })


@app.route('/api/events')
def api_events():
    with db() as conn:
        rows = conn.execute('''SELECT e.*, COUNT(r.id) AS rsvp_count
                              FROM events e LEFT JOIN rsvps r ON r.event_id=e.id
                              GROUP BY e.id ORDER BY e.date ASC, e.start_time ASC, e.id ASC''').fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/events', methods=['POST'])
@manager_required
def create_event():
    data = request.get_json(silent=True) or {}
    required = ['title', 'date', 'start_time']
    if any(not str(data.get(k, '')).strip() for k in required):
        return jsonify({'error': 'Title, date and start time are required.'}), 400
    try:
        capacity = max(0, int(data.get('capacity') or 0))
    except ValueError:
        capacity = 0
    with db() as conn:
        cur = conn.execute('''INSERT INTO events
            (title,description,category,department,date,start_time,end_time,location,postal,capacity,host,featured,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                str(data.get('title','')).strip(), str(data.get('description','')).strip(),
                str(data.get('category','Community')).strip(), str(data.get('department','General')).strip(),
                str(data.get('date','')).strip(), str(data.get('start_time','')).strip(), str(data.get('end_time','')).strip(),
                str(data.get('location','')).strip(), str(data.get('postal','')).strip(), capacity,
                str(data.get('host','')).strip(), 1 if data.get('featured') else 0,
                datetime.utcnow().isoformat(timespec='seconds') + 'Z'
            ))
    return jsonify({'ok': True, 'id': cur.lastrowid}), 201


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@manager_required
def delete_event(event_id):
    with db() as conn:
        conn.execute('DELETE FROM rsvps WHERE event_id=?', (event_id,))
        cur = conn.execute('DELETE FROM events WHERE id=?', (event_id,))
    if not cur.rowcount:
        return jsonify({'error': 'Event not found'}), 404
    return jsonify({'ok': True})


@app.route('/api/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
def rsvp(event_id):
    user = session['discord_user']
    with db() as conn:
        event = conn.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        count = conn.execute('SELECT COUNT(*) FROM rsvps WHERE event_id=?', (event_id,)).fetchone()[0]
        existing = conn.execute('SELECT id FROM rsvps WHERE event_id=? AND user_id=?', (event_id, user['id'])).fetchone()
        if existing:
            conn.execute('DELETE FROM rsvps WHERE id=?', (existing['id'],))
            return jsonify({'ok': True, 'rsvped': False})
        if event['capacity'] and count >= event['capacity']:
            return jsonify({'error': 'This event is full.'}), 409
        conn.execute('INSERT INTO rsvps(event_id,user_id,username,created_at) VALUES(?,?,?,?)',
                     (event_id, user['id'], user['username'], datetime.utcnow().isoformat(timespec='seconds') + 'Z'))
    return jsonify({'ok': True, 'rsvped': True})


if __name__ == '__main__':
    port = int(os.getenv('PORT', '3000'))
    app.run(host='0.0.0.0', port=port, debug=False)
