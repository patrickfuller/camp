"""
Creates an HTTP server with basic auth and websocket communication.
"""
import argparse
import base64
import cStringIO
import hashlib
import json
import os
import time
import webbrowser

import tornado.web
import tornado.websocket
from tornado.ioloop import PeriodicCallback

import cv2
from PIL import Image

camera = cv2.VideoCapture(0)

# Hashed password for comparison and a cookie for login cache
ROOT = os.path.normpath(os.path.dirname(__file__))
with open(os.path.join(ROOT, "password.txt")) as in_file:
    PASSWORD = in_file.read().strip()
COOKIE_NAME = "campi"


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        if not self.get_secure_cookie(COOKIE_NAME):
            self.redirect("/login")
        else:
            self.render("index.html", port=args.port)


class LoginHandler(tornado.web.RequestHandler):

    def get(self):
        self.render("login.html")

    def post(self):
        password = self.get_argument("password", "")
        if hashlib.sha512(password).hexdigest() == PASSWORD:
            self.set_secure_cookie(COOKIE_NAME, str(time.time()))
            self.redirect("/")
        else:
            time.sleep(1)
            self.redirect(u"/login?error")


class WebSocket(tornado.websocket.WebSocketHandler):

    def on_message(self, message):
        """Evaluates the function pointed to by json-rpc."""
        json_rpc = json.loads(message)

        # Start an infinite loop when this is called
        if json_rpc["method"] == "read_camera":
            delay = 1000.0 / json_rpc["frame_rate"]
            self.camera_loop = PeriodicCallback(self.loop, delay)
            self.camera_loop.start()

        # Extensibility for other methods
        else:
            print("Unsupported function: " + message["method"])

    def loop(self):
        """Sends camera images in an infinite loop."""
        sio = cStringIO.StringIO()
        _, frame = camera.read()
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img.save(sio, "JPEG")
        try:
            self.write_message(base64.b64encode(sio.getvalue()))
        except tornado.websocket.WebSocketClosedError:
            self.camera_loop.stop()


parser = argparse.ArgumentParser(description="Starts a webserver that "
                                 "connects to a webcam.")
parser.add_argument("--port", type=int, default=8000, help="The "
                    "port on which to serve the website.")
parser.add_argument("--resolution", type=str, default="low", help="The "
                    "video resolution. Can be high, medium, or low.")
args = parser.parse_args()

# Use default camera option if 'high'. Scale down if 'medium' or 'low'.
if args.resolution == "high":
    pass
elif args.resolution == "medium":
    camera.set(3, 640)
    camera.set(4, 480)
elif args.resolution == "low":
    camera.set(3, 320)
    camera.set(4, 240)
else:
    raise Exception("%s not in resolution options." % args.resolution)

handlers = [(r"/", IndexHandler), (r"/login", LoginHandler),
            (r"/websocket", WebSocket),
            (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': ROOT})]
application = tornado.web.Application(handlers, cookie_secret=PASSWORD)
application.listen(args.port)

webbrowser.open("http://localhost:%d/" % args.port, new=2)

tornado.ioloop.IOLoop.instance().start()
