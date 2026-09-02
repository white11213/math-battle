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
    
    # === 独自の問題リスト（ご自身の問題リストをここにコピペしてください） ===
    samples = [
            ("$\\int (3x^2 - 3x + 2) dx$ の極小値を求めよ。", "0", 60),
            ("$\\sum_{k=1}^{n} k^2$ の値を求めよ。", "n(n+1)(2n+1)/6", 60)
            (r"方程式 $\log_2(x) + \log_2(x-3) = 2$ を解け。", "4", 60),
            (r"定積分 $\int_0^1 x^2 \, dx$ の値を求めよ。", "1/3", 60),
            (r"初項 $2$、公差 $3$ の等差数列の第10項を求めよ。", "29", 60),
            (r"2次方程式 $2x^2 - 5x + 2 = 0$ の解のうち、小さい方の値を求めよ。（入力例: 1/2）", "1/2", 90)    
     　　　 (r"関数 $f(x) = x^3 - 3x^2 + 4$ の極小値を求めよ。", "0", 60),
            (r"極限 $\lim_{n \to \infty} \frac{1}{n^2} \sum_{k=1}^{n} k^2$ の値を求めよ。（入力例: 1/3）", "1/3", 60),
            (r"方程式 $\log_2(x) + \log_2(x-3) = 2$ を解け。", "4", 60),
            (r"定積分 $\int_0^1 x^2 \cdot e^x dx$ の値を求めよ。", "e-2", 90),
            (r"初項 $2$、公差 $3$ の等差数列の第10項を求めよ。", "29", 45),
            (r"ベクトル $\vec{a}=(2,1)$, $\vec{b}=(1,3)$ のなす角 $\theta$ を求めよ。（$0^\circ \le \theta \le 180^\circ$）", "45", 60),
            (r"方程式 $z^3 = 1$ の虚数解のうち、虚部が正であるものを $\omega$ とする。$\omega^2 + \omega + 1$ の値を求めよ。", "0", 60),
            (r"放物線 $y = x^2$ と直線 $y = 2x + 3$ で囲まれた部分の面積を求めよ。（入力例: 32/3）", "32/3", 90),
            (r"赤球4個、白球6個が入った袋から同時に3個を取り出すとき、少なくとも1個が赤球である確率を求めよ。（入力例: 5/6）", "5/6", 60),
            (r"不等式 $|2x - 5| \le 3$ を満たす整数 $x$ の個数を求めよ。", "4", 45)
            (r"曲線 $y = e^x$ 上の点 $(1, e)$ における接線と $x$ 軸、$y$ 軸で囲まれた部分の面積を求めよ。（入力例: e/4）", "e/4", 90),
            (r"$0 \le x \le \pi$ において、関数 $f(x) = \sin^3 x + \cos^3 x$ の最大値を求めよ。", "1", 90),
            (r"行列 $A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}$ のトレース（対角成分の和）を求めよ。", "5", 60),
            (r"1個のサイコロをn回投げるとき、出た目の積が5の倍数となる確率が0.99以上となる最小のnを求めよ。", "21", 120),
            (r"極限 $\lim_{x \to 0} \frac{e^{2x} - 1 - 2x}{x^2}$ の値を求めよ。", "2", 90),
            (r"方程式 $z^4 = -1$ の解のうち、複素数平面上で第1象限にあるものを求めよ。", "(1+i)/sqrt(2)", 120),
            (r"放物線 $y = x^2$ 上の点 $(1, 1)$ における法線と、この放物線で囲まれた部分の面積を求めよ。", "4/3", 90) 
            (r"定積分 $\int_0^{\pi/2} \sin^3 x \, dx$ の値を求めよ。", "2/3", 60),
            (r"曲線 $y = x \log x$ の極小値を求めよ。（入力例: -1/e）", "-1/e", 90),
            (r"極限 $\lim_{x \to 0} \frac{1 - \cos 3x}{x^2}$ の値を求めよ。", "9/2", 60),
            (r"1から9までの番号がついたカードから同時に2枚を選ぶとき、その積が偶数となる確率を求めよ。", "13/18", 60),
            (r"A, B, C, D, E の5人が1列に並ぶとき、AとBが隣り合わない確率を求めよ。", "3/5", 60),
            (r"三角形ABCにおいて $AB=3, BC=4, CA=2$ のとき、$\cos \angle A$ の値を求めよ。", "-1/4", 60),
            (r"点 $(2, 3)$ から円 $x^2 + y^2 = 1$ に引いた2本の接線のなす角を $\theta$ とするとき、$\tan \frac{\theta}{2}$ の値を求めよ。", "1/\sqrt{12}", 90),
            (r"漸化式 $a_1=1, a_{n+1} = 2a_n + 1$ で定まる数列の一般項 $a_n$ に対し、$a_6$ の値を求めよ。", "63", 60),
            (r"和 $\sum_{k=1}^{n} k \cdot 2^k$ において、$n=5$ のときの実数値を求めよ。", "258", 90),      
            (r"方程式 $x^3 - 3x^2 + 3x - 1 = 0$ の解を求めよ。", "1", 45),
            (r"複素数 $z = \frac{1 + \sqrt{3}i}{2}$ のとき、$z^6$ の値を求めよ。", "1", 60)

    ]
    # ====================================================================

    # 未登録の問題のみ安全に追加
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
    print("Start game requested with data:", data)
    q_count = 3
    if isinstance(data, dict) and 'q_count' in data:
        try:
            q_count = int(data['q_count'])
        except (ValueError, TypeError):
            q_count = 3
    elif isinstance(data, (int, str)):
        try:
            q_count = int(data)
        except (ValueError, TypeError):
            q_count = 3

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM questions")
    all_q = c.fetchall()
    conn.close()

    if not all_q:
        print("Error: No questions in database!")
        return

    # データベースの問題数が要求数より少ない場合のフォールバック
    if len(all_q) < q_count:
        q_count = len(all_q)

    game_state['current_questions'] = random.sample(all_q, q_count)
    game_state['current_q_index'] = 0
    game_state['is_playing'] = True
    
    for p in game_state['players'].values():
        p['score'] = 0
        p['answered'] = False

    print(f"Game starting with {q_count} questions.")
    send_next_question()

def send_next_question():
    for p in game_state['players'].values():
        p['answered'] = False
    game_state['finish_count'] = 0
    
    q = game_state['current_questions'][game_state['current_q_index']]
    print(f"Sending question: {q[1]}")
    
    # クライアントへ問題を送信 (q[0]:id, q[1]:text, q[2]:answer, q[3]:time_limit)
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
        
    # 半数以上が解答したら次の問題へ
    threshold = math.ceil(len(game_state['players']) / 2.0)
    if game_state['finish_count'] >= threshold:
        game_state['current_q_index'] += 1
        if game_state['current_q_index'] < len(game_state['current_questions']):
            send_next_question()
        else:
            game_state['is_playing'] = False
            print("Game Over")
            emit('game_over', get_leaderboard(), broadcast=True)

def get_leaderboard():
    return sorted(game_state['players'].values(), key=lambda x: x['score'], reverse=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in game_state['players']:
        name = game_state['players'][sid]['name']
        del game_state['players'][sid]
        print(f"Player disconnected: {name}")
        emit('update_players', get_leaderboard(), broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)