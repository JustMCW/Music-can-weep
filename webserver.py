import flask
import threading

app = flask.Flask("")

@app.route("/")
def home():
    return "running"

def run():
    app.run(host="0.0.0.0",port=8000)

def init():
    #In repl, remember to :
    # install ffmpeg : by tying "ffmpeg" in the shell
    # install opus   : download it from local pc
    # install PyNaCl : entering "pip install PyNaCl" in the shell
    
    # run this init function and ping it in https://uptimerobot.com/dashboard#792948581 to 
    
    threading.Thread(target=run).start()

