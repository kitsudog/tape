#!env python
# -*- coding:utf-8 -*-
import sys
import time
import tkMessageBox
from contextlib import closing

import requests

typemap = {
    'hd': u"超清版本",
    'ud': u"高清版本",
    'sd': u"标清版本",
    'ld': u"流畅版本",
}


def get(fout, url):
    with closing(requests.get(url, stream=True, timeout=(60, 600))) as r:
        stream = r.raw
        size = 0
        buff = []
        end = False
        expire = time.time() + 1
        while not end:
            if time.time() > expire:
                expire = time.time() + 1
                sys.stdout.write('.')
                sys.stdout.flush()
            chunk = stream.read(10 * 1024)
            size += len(chunk)
            buff.extend(chunk)
            if len(buff) > 100 * 1024:
                fout.write(bytearray(buff))
                buff = []
            if stream.closed:
                end = True


def main(share_url):
    vid = re.compile('(\d+)\.swf').findall(share_url)[0]
    info = requests.get('http://cloud.video.taobao.com/videoapi/info.php?vid=%s' % vid)
    for video in re.compile('<video>.+?</video>').findall(info.content):
        try:
            url = re.compile('<video_url>(.+?)</video_url>').findall(video)[0]
            length = re.compile('<length>(\d+)</length>').findall(video)[0]
            vtype = re.compile('<type>(.+)</type>').findall(video)[0]
            sys.stdout.write(u"获取[%s]" % typemap[vtype])
            sys.stdout.flush()
            if int(length) > 20 * 1000 * 1000:
                print u"[文件过大跳过]"
                continue
            with open('%s.flv' % vtype, mode='wb') as fout:
                get(fout, '%s/start_0/end_%s/1.flv' % (url, length))
            print "[SUCC]"
        except:
            print "[FAIL]"


if __name__ == '__main__':
    if sys.platform == 'win32':
        from Tkinter import *

        root = Tk()


        def submit():
            try:
                main(shuru.get())
                tkMessageBox.showinfo(u"提示", u"结束请查看")
            except:
                tkMessageBox.showinfo(u"提示", u"出现错误了")
            sys.exit(1)


        l = Label(root, text=u'输入分享的地址')
        shuru = Entry(root)
        anniu = Button(root, text=u'开始', command=submit)

        l.pack()
        shuru.pack()
        anniu.pack()

        root.mainloop()
    else:
        if len(sys.argv) < 2:
            print u"请导入分享链接"
            sys.exit(0)
        main(sys.argv[1])
