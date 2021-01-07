#!/usr/bin/env python
"""
Creates an HTTP server with basic auth and websocket communication.
"""
import argparse
import base64
import hashlib
import os
import time
import threading
import webbrowser

try:
    import cStringIO as io
except ImportError:
    import io

import tornado.web
import tornado.websocket
from tornado.ioloop import PeriodicCallback

# Hashed password for comparison and a cookie for login cache
ROOT = os.path.normpath(os.path.dirname(__file__))
with open(os.path.join(ROOT, "password.txt")) as in_file:
    PASSWORD = in_file.read().strip()
COOKIE_NAME = "camp"


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        if args.require_login and not self.get_secure_cookie(COOKIE_NAME):
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


class ErrorHandler(tornado.web.RequestHandler):
    def get(self):
        self.send_error(status_code=403)


class WebSocket(tornado.websocket.WebSocketHandler):

    def on_message(self, message):
        """Evaluates the function pointed to by json-rpc."""

        # Start an infinite loop when this is called
        if message == "read_camera":
            if not args.require_login or self.get_secure_cookie(COOKIE_NAME):
                self.camera_loop = PeriodicCallback(self.loop, 10)
                self.camera_loop.start()
            else:
                print("Unauthenticated websocket request")

        # Extensibility for other methods
        else:
            print("Unsupported function: " + message)

    def loop(self):
        """Sends camera images in an infinite loop."""
        try:
            sio = io.BytesIO() # for Python3
        except AttributeError:
            sio = io.StringIO()  # for Python2

        if args.use_usb:
            _, frame = camera.read()
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            img.save(sio, "JPEG")
        else:
            camera.capture(sio, "jpeg", use_video_port=True)

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
parser.add_argument("--require-login", action="store_true", help="Require "
                    "a password to log in to webserver.")
parser.add_argument("--use-usb", action="store_true", help="Use a USB "
                    "webcam instead of the standard Pi camera.")
parser.add_argument("--usb-id", type=int, default=0, help="The "
                     "usb camera number to display")
args = parser.parse_args()

if args.use_usb:
    import cv2
    from PIL import Image
    camera = cv2.VideoCapture(args.usb_id)
else:
    import picamera
    camera = picamera.PiCamera()
    camera.start_preview()

resolutions = {"high": (1280, 720), "medium": (640, 480), "low": (320, 240)}
if args.resolution in resolutions:
    if args.use_usb:
        w, h = resolutions[args.resolution]
        camera.set(3, w)
        camera.set(4, h)
    else:
        camera.resolution = resolutions[args.resolution]
else:
    raise Exception("%s not in resolution options." % args.resolution)

handlers = [(r"/", IndexHandler), (r"/login", LoginHandler),
            (r"/websocket", WebSocket),
            (r"/static/password.txt", ErrorHandler),
            (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': ROOT})]
application = tornado.web.Application(handlers, cookie_secret=PASSWORD)
application.listen(args.port)

webbrowser.open("http://localhost:%d/" % args.port, new=2)

tornado.ioloop.IOLoop.instance().start()
