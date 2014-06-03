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
PASSWORD = ("fcb109fa2283b3ba51640e3c93b0307ac6332e5c1434d1b330be513373e65480"
            "8223797aab1c09be4feba61cc06f2569a93c314e74052f6098b5b8331256967a")
COOKIE_NAME = "labcamera"
COOKIE_SECRET = "3RYBOfCdQpevL/OqUK8El1xZgHwQJUcsuOpBR1DY06o="


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
        self.write_message(base64.b64encode(sio.getvalue()))


parser = argparse.ArgumentParser(description="Starts a webserver that "
                                 "connects to a webcam.")
parser.add_argument("--port", type=int, default=16000, help="The "
                    "port on which to serve the website.")
args = parser.parse_args()

handlers = [(r"/", IndexHandler), (r"/login", LoginHandler),
            (r"/websocket", WebSocket),
            (r'/static/(.*)', tornado.web.StaticFileHandler,
             {'path': os.path.normpath(os.path.dirname(__file__))})]
application = tornado.web.Application(handlers, cookie_secret=COOKIE_SECRET)
application.listen(args.port)

webbrowser.open("http://localhost:%d/" % args.port, new=2)

tornado.ioloop.IOLoop.instance().start()
