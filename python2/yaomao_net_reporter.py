#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re

import pymysql
import time
import sys

reload(sys)
sys.setdefaultencoding('utf-8')


def main(dst):
    conn = pymysql.connect(host='192.168.1.100', user='root', passwd='root', db='net', charset='utf8')
    cur = conn.cursor()
    human_map = {}
    cur.execute('SELECT `mac`, `human` FROM `reg`')
    for info in cur:
        human_map[info[0]] = info[1]

    cur.execute('''\
SELECT `mac`,(max(`download`)-min(`download`)) AS `byte`
FROM `log`
WHERE `time`=%s OR `time`=%s
GROUP BY mac
HAVING count(1)=2 AND `byte` >1000
ORDER BY `byte` DESC
''' % (dst, dst - 1))

    data = []
    for info in cur:
        mac, download = info
        data.append((mac, download))

    sql = []
    for mac, download in data:
        if download > 1000 * 1024 * 1024:
            # 太大的
            continue
        if download < 1024:
            # 太小的
            continue
        sql.append('INSERT INTO `log2` (`logtime`,`mac`,`download`) VALUES (%s, "%s", %s)' % (dst, mac, download))
    try:
        cur.execute(';'.join(sql))
    except Exception as e:
        sys.stderr.write("插入时出错[%s]\n" % e)
    finally:
        conn.commit()

    content = ''
    for mac, download in data:
        download /= 1024
        floor, mac = re.compile('([^_]+)_(.+)').findall(mac)[0]
        human = human_map[mac] if mac in human_map else mac
        is_route = human.find('路由') >= 0
        if is_route:
            continue
        if download == 0:
            continue
        elif download < 1024:
            content += '<tr><td>[%s] %s</td><td>%s</td><td>KB</td></tr>\n' % (floor, human, download)
        elif download < 12 * 1024:
            content += '<tr><td>[%s] %s</td><td>%s</td><td>MB</td></tr>\n' % (floor, human, download / 1024)
        elif download < 1000 * 1024:
            content += '''\
<tr><td><font color='red'><b><h3>[%s] %s</h3></b></font></td>
<td><font color='red'><b><h3>%s</h3></b></font></td>
<td><font color='red'><b><h3>MB</h3></b></font></td></tr>
''' % (floor, human, download / 1024)
        else:
            # 数据过大了
            continue

    sys.stdout.write('''\
<meta charset="utf-8" />
<meta http-equiv="refresh" content="60" />
<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
<h1><b>截止 %s</b></h1>
<table>
<tr><th>使用者</th><th>1min总流量</th><th></th><tr>
%s\
</table>
''' % (time.strftime('%H:%M'), content))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        dst = sys.argv[1]
    else:
        dst = time.strftime('%y%j%H%M')
    main(int(dst))
