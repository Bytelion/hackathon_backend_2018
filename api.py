import json
import random
from threading import Lock

from flask import Flask, jsonify, request, render_template, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room, rooms, disconnect
import requests
import redis
import eventlet


redis = redis.StrictRedis(host="localhost", port=6379, db=0)

RPC_URL = "http://bytecoinrpc:8jjqSWVyaLEzJhKPT3vV7aoPGzNmS9ZLNfoAtYe1RJhw@127.0.0.1:9332"

async_mode = "eventlet"

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, async_mode=async_mode)

thread = None
thread_lock = Lock()


@app.route("/")
def hello():
    return "Hello World!"

@app.route("/sample_json")
def sample_json():
    name = request.args.get("name")
    data = {
        "name": name if name else "empty",
        "greeting": "Hello, {}".format(name if name else "world"),
        "message": "You're using query parameters" if name else "You should try using query parameters!"
    }
    return jsonify(data)

@app.route("/daemon_stats")
def bytecoin_stats():
    data = {
        "method": "getinfo",
    }
    response = requests.post(RPC_URL, data=json.dumps(data))
    return response.text

def get_bytecoin_price():
    last_price = redis.get("bytecoin_price")
    if last_price >= 350:
        diff = -50
    elif last_price <= 122:
        diff = 32
    else:
        diff = random.randint(-5, 5)
    redis.set("bytecoin_price", last_price + diff)
    return redis.get("bytecoin_price")

def background_thread():
    """Send server generated events to clients."""
    while True:
        socketio.sleep(1)
        data = {
            "miner_count": redis.get("num_miners"),
            "bytecoin_price": get_bytecoin_price(),
            "total_work": redis.get("combined_mining_speed")
        }
        socketio.emit("stats", data, namespace="/bytecoin")

@socketio.on("connect", namespace="/bytecoin")
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)

@socketio.on("add_miner", namespace="/bytecoin")
def add_miner():
    redis.incr("num_miners")

@socketio.on("subtract_miner", namespace="/bytecoin")
def subtract_miner():
    miner_count = redis.get("num_miners")
    if miner_count > 0:
        redis.decr("num_miners")

@socketio.on("add_mining_speed", namespace="/bytecoin")
def add_mining_speed(mining_speed):
    redis.incrby("combined_mining_speed", mining_speed)

@socketio.on("subtract_mining_speed", namespace="/bytecoin")
def subtract_mining_speed(mining_speed):
    combined_mining_speed = redis.get("combined_mining_speed")
    if combined_mining_speed > 0:
        redis.decr("combined_mining_speed", mining_speed)


if __name__ == "__main__":
    socketio.run(app, "0.0.0.0", 8080, debug=True)
