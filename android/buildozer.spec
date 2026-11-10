[app]
title = dSOS
package.name = dsos
package.domain = org.taru8899
source.dir = .
source.include_exts = py,png,jpg
version = 0.2.0
requirements = python3,kivy==2.3.0,requests,urllib3,chardet,idna,certifi,charset-normalizer,pycryptodome
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/logo.png
presplash.filename = %(source.dir)s/logo.png
android.presplash_color = #04A835
android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
