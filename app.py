import os
import sqlite3
import math
import random
from fractions import Fraction
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_FILE = 'math_battle.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            answer TEXT,
            time_limit INTEGER
        )
    ''')
    
    samples = [
        ("関数 $f(x) = x^3 - 3x^2 + 4$ の極小値を求めよ。", "0", 60),
        ("$\\int (3x^2 - 3x + 2) dx$ の極小値を求めよ。", "0", 60),
        ("$\\sum_{k=1}^{n} k^2$ の値を求めよ。", "n(n+1)(2n+1)/6", 60)
    ]

    for text, answer, time_limit in samples:
        c.execute("SELECT COUNT(*) FROM questions WHERE text = ?", (text,))
        if c.fetchone()[0] == 0:
            c.execute(
                "INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)",
                (text, answer, time_limit)
            )
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

init_db()

game_state = {
    'is_playing': False,
    'players': {},
    'current_questions': [],
    'current_q_index': 0,
    'finish_count': 0
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    sid = request.sid
    name = data.get('name', 'Anonymous')
    game_state['players'][sid] = {'name': name, 'score': 0, 'answered': False}
    print(f"Player joined: {name} (SID: {sid})")
    emit('update_players', get_leaderboard(), broadcast=True)

@socketio.on('add_question')
def handle_add_q(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)",
              (data['text'], data['answer'].strip(), int(data['time'])))
    conn.commit()
    conn.close()
    print("New question added manually.")

@socketio.on('start_game')
def handle_start(data=None):
    q_count = 3
    if isinstance(data, dict) and 'q_count' in data:
        try:
            q_count = int(data['q_count'])
        except (ValueError, TypeError):
            q_count = 3

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM questions")
    all_q = c.fetchall()
    conn.close()

    if not all_q:
        return

    if len(all_q) < q_count:
        q_count = len(all_q)

    game_state['current_questions'] = random.sample(all_q, q_count)
    game_state['current_q_index'] = 0
    game_state['is_playing'] = True
    
    for p in game_state['players'].values():
        p['score'] = 0
        p['answered'] = False

    send_next_question()

def send_next_question():
    for p in game_state['players'].values():
        p['answered'] = False
    game_state['finish_count'] = 0
    
    q = game_state['current_questions'][game_state['current_q_index']]
    emit('new_question', {'id': q[0], 'text': q[1], 'time_limit': q[3]}, broadcast=True)
    emit('update_players', get_leaderboard(), broadcast=True)

def check_math_answer(user_ans, correct_ans):
    try:
        if user_ans.strip() == correct_ans.strip():
            return True
        return Fraction(user_ans) == Fraction(correct_ans)
    except:
        return False

@socketio.on('submit_answer')
def handle_answer(data):
    sid = request.sid
    if not game_state['is_playing'] or sid not in game_state['players']:
        return
    if game_state['players'][sid].get('answered', True):
        return
    
    q = game_state['current_questions'][game_state['current_q_index']]
    game_state['players'][sid]['answered'] = True
    game_state['finish_count'] += 1
    
    is_correct = check_math_answer(data['answer'], q[2])
    if is_correct:
        game_state['players'][sid]['score'] += 1
        
    emit('answer_result', {'correct': is_correct}, to=sid)
        
    threshold = math.ceil(len(game_state['players']) / 2.0)
    if game_state['finish_count'] >= threshold:
        game_state['current_q_index'] += 1
        if game_state['current_q_index'] < len(game_state['current_questions']):
            send_next_question()
        else:
            game_state['is_playing'] = False
            emit('game_over', get_leaderboard(), broadcast=True)

def get_leaderboard():
    return sorted(game_state['players'].values(), key=lambda x: x['score'], reverse=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in game_state['players']:
        del game_state['players'][sid]
        emit('update_players', get_leaderboard(), broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)