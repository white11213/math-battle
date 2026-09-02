import sqlite3
import random
import math
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_FILE = 'math_battle.db'

# データベースの初期化とサンプル問題（偏差値60レベル）の投入
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS questions 
                 (id INTEGER PRIMARY KEY, text TEXT, answer TEXT, time_limit INTEGER)''')
    
    # データが空ならサンプルを追加（微積、整数、極限など）
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        samples = [
            (r"関数 $f(x) = x^3 - 3x^2 + 4$ の極小値を求めよ。", "0", 60),
            (r"$x, y$ を自然数とする。$x^2 - y^2 = 21$ を満たす $(x, y)$ のうち $x$ の最大値を求めよ。", "11", 90),
            (r"極限 $\lim_{n \to \infty} \frac{1}{n^3} \sum_{k=1}^n k^2$ の値を求めよ。（分数入力例: 1/3）", "1/3", 60),
            (r"方程式 $\log_2(x) + \log_2(x-3) = 2$ を解け。", "4", 60),
            (r"3点 $A(0,0), B(4,0), C(1,\sqrt{3})$ を頂点とする三角形の面積を求めよ。", "2\sqrt{3}", 90)
        ]
        c.executemany("INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)", samples)
    conn.commit()
    conn.close()

init_db()

# ゲームの進行状態を管理する変数
game_state = {
    'is_playing': False,
    'players': {}, # {sid: {'name': 'Player1', 'score': 0, 'answered': False}}
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
    name = data['name']
    game_state['players'][sid] = {'name': name, 'score': 0, 'answered': False}
    emit('update_players', get_leaderboard(), broadcast=True)

@socketio.on('add_question')
def handle_add_q(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)", 
              (data['text'], data['answer'], int(data['time'])))
    conn.commit()
    conn.close()

@socketio.on('start_game')
def handle_start(data):
    q_count = int(data['q_count'])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM questions")
    all_q = c.fetchall()
    conn.close()
    
    if len(all_q) < q_count:
        q_count = len(all_q)
        
    game_state['current_questions'] = random.sample(all_q, q_count)
    game_state['current_q_index'] = 0
    game_state['is_playing'] = True
    for p in game_state['players'].values():
        p['score'] = 0
    
    send_next_question()

def send_next_question():
    for p in game_state['players'].values():
        p['answered'] = False
    game_state['finish_count'] = 0
    
    q = game_state['current_questions'][game_state['current_q_index']]
    emit('new_question', {'q_text': q[1], 'time_limit': q[3]}, broadcast=True)
    emit('update_players', get_leaderboard(), broadcast=True) # 途中順位表示

@socketio.on('submit_answer')
def handle_answer(data):
    sid = request.sid
    if not game_state['is_playing'] or game_state['players'][sid]['answered']:
        return

    q = game_state['current_questions'][game_state['current_q_index']]
    game_state['players'][sid]['answered'] = True
    game_state['finish_count'] += 1
    
    # 正誤判定
    if data['answer'].strip() == q[2].strip():
        game_state['players'][sid]['score'] += 1
        emit('answer_result', {'correct': True})
    else:
        emit('answer_result', {'correct': False})

    # 上位50%が解き終わったか判定
    threshold = math.ceil(len(game_state['players']) / 2.0)
    if game_state['finish_count'] >= threshold:
        game_state['current_q_index'] += 1
        if game_state['current_q_index'] < len(game_state['current_questions']):
            send_next_question()
        else:
            game_state['is_playing'] = False
            emit('game_over', get_leaderboard(), broadcast=True)

def get_leaderboard():
    # スコア順に並び替え
    board = sorted(game_state['players'].values(), key=lambda x: x['score'], reverse=True)
    return board

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in game_state['players']:
        del game_state['players'][sid]
        emit('update_players', get_leaderboard(), broadcast=True)

if __name__ == '__main__':
    # 0.0.0.0で起動し、同一Wi-Fi内のスマホからアクセス可能にする
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)