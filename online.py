#ignore this , i copy this from somewhere else (just for keeping online)

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return (
      "<h1>WEB SERVER</h1>"\
      "<p>Don't spy my bot lol<br>Rick Astley said that :) </p>"\
      "<img src='https://cdn.vox-cdn.com/thumbor/qOHrtk0OiV4iKL_z7fyEgTwcRqk=/0x44:1268x889/1820x1213/filters:focal(0x44:1268x889):format(webp)/cdn.vox-cdn.com/uploads/chorus_image/image/47684009/Screenshot_2014-07-19_15.24.57.0.png' width=200 height=100>"
      )

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_online():
    Thread(target=run).start()
    print("Web server is set")
