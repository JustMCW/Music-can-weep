#ignore this , i copy this from somewhere else (just for keeping online)

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Hello. I am alive!"

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    print("Web server working")
    t = Thread(target=run)
    t.start()