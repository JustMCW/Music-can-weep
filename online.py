#ignore this , i copy this from somewhere else (just for keeping online)

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "web"
def run():
  app.run(host='0.0.0.0',port=8080)

def keep_online():
    Thread(target=run).start()
    print("Web server is set")
