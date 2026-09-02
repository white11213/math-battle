from gevent import monkey
monkey.patch_all()
import sqlite3
import random
import math
from fractions import Fraction
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
DB_FILE = 'math_battle.db'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
def init_db():

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS questions 
                 (id INTEGER PRIMARY KEY, text TEXT, answer TEXT, time_limit INTEGER)''')
    
    # 整数と分数が混ざったサンプル問題（偏差値60レベル）
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        samples = [
            (r"関数 $f(x) = x^3 - 3x^2 + 4$ の極小値を求めよ。", "0", 60),
            (r"極限 $\lim_{n \to \infty} \frac{1}{n^3} \sum_{k=1}^n k^2$ の値を求めよ。（入力例: 1/3）", "1/3", 60),
            (r"方程式 $\log_2(x) + \log_2(x-3) = 2$ を解け。", "4", 60),
            (r"定積分 $\int_0^1 x^2 \, dx$ の値を求めよ。（入力例: 1/3）", "1/3", 60),
            (r"初項 $2$、公差 $3$ の等差数列の第10項を求めよ。", "29", 60),
            (r"2次方程式 $2x^2 - 5x + 2 = 0$ の解のうち、小さい方の値を求めよ。（入力例: 1/2）", "1/2", 90)
        ]
        c.executemany("INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)", samples)
    conn.commit()
    conn.close()

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
    name = data['name']
    game_state['players'][sid] = {'name': name, 'score': 0, 'answered': False}
    emit('update_players', get_leaderboard(), broadcast=True)

@socketio.on('add_question')
def handle_add_q(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO questions (text, answer, time_limit) VALUES (?, ?, ?)", 
              (data['text'], data['answer'].strip(), int(data['time'])))
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
    emit('update_players', get_leaderboard(), broadcast=True)

# 整数や分数を柔軟に判定する関数
def check_math_answer(user_ans, correct_ans):
    user_ans = user_ans.strip()
    correct_ans = correct_ans.strip()
    if user_ans == correct_ans:
        return True
    
    try:
        # PythonのFraction（分数ライブラリ）を使って、値として等しいか判定する
        # 例: "2/4" と "1/2" や、"3" と "3/1" を同じものとみなす
        if Fraction(user_ans) == Fraction(correct_ans):
            return True
    except:
        pass
    
    return False

@socketio.on('submit_answer')
def handle_answer(data):
    sid = request.sid
    if not game_state['is_playing'] or game_state['players'][sid]['answered']:
        return

    q = game_state['current_questions'][game_state['current_q_index']]
    game_state['players'][sid]['answered'] = True
    game_state['finish_count'] += 1
    
    # 柔軟な正誤判定を実行
    if check_math_answer(data['answer'], q[2]):
        game_state['players'][sid]['score'] += 1
        emit('answer_result', {'correct': True})
    else:
        emit('answer_result', {'correct': False})

    threshold = math.ceil(len(game_state['players']) / 2.0)
    if game_state['finish_count'] >= threshold:
        game_state['current_q_index'] += 1
        if game_state['current_q_index'] < len(game_state['current_questions']):
            send_next_question()
        else:
            game_state['is_playing'] = False
            emit('game_over', get_leaderboard(), broadcast=True)

def get_leaderboard():
    board = sorted(game_state['players'].values(), key=lambda x: x['score'], reverse=True)
    return board

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in game_state['players']:
        del game_state['players'][sid]
        emit('update_players', get_leaderboard(), broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)