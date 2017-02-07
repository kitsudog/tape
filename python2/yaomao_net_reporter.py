#!/usr/bin/env python
# -*- coding:utf-8 -*-
import J
import re
from collections import OrderedDict

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
        conn.commit()
    except Exception as e:
        sys.stderr.write("插入时出错[%s]\n" % e)

    STEP = 30
    cur.execute('SELECT `logtime`, `mac`,`download` FROM `log2` WHERE `logtime` BETWEEN %d AND %d' % (dst - STEP, dst))

    log2 = {}
    for logtime, mac, download in cur:
        if mac not in log2:
            log2[mac] = [0] * STEP
        log2[mac][logtime - dst + STEP - 1] = download

    for mac in filter(lambda x: max(log2[x]) < 10 * 1024 * 1024, log2.keys()):
        del log2[mac]

    orig_keys = log2.keys()
    orig_keys = sorted(orig_keys, key=lambda x: sum(log2[x]), reverse=True)
    orig_log2 = log2
    log2 = OrderedDict()
    for key in orig_keys:
        floor, mac = re.compile('([^_]+)_(.+)').findall(key)[0]
        human = human_map[mac] if mac in human_map else mac
        is_route = human.find('路由') >= 0
        if is_route:
            continue
        log2[key] = orig_log2[key]

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
<!DOCTYPE html>
<html>
<meta charset="utf-8" />
<meta http-equiv="refresh" content="60" />
<meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
<script src='static/echarts.min.js'>
</script>
<script type='text/javascript'>
    var human = %s;
    var log2 = %s;
    function human_size(size){
        if (size<1024){
            return size + 'B';
        } else if (size<1024*1024){
            return Math.floor(size/1024) + 'KB';
        } else if (size<1024*1024*1024){
            return Math.floor(size/1024/1024) + 'MB';
        } else {
            return Math.floor(size/1024/1024/1024) + 'GB';
        }
    }
</script>
<h1><b>截止 %s</b></h1>
<div id="content">
<div id="table">
<table>
<tr><th>使用者</th><th>1min总流量</th><th></th><tr>
%s\
</table>
</div>
<div id="charts" style="width: 100%%; height: 400px;">
</div>
</div>
<script type="text/javascript">
    var option = {
        title: {
            text: '内网网络情况'
        },
        tooltip : {
            trigger: 'axis'
        },
        grid: {
            left: '3%%',
            right: '4%%',
            bottom: '3%%',
            containLabel: true
        },
        xAxis : [
            {
                type : 'category',
                boundaryGap : false,
                // data : ['周一','周二','周三','周四','周五','周六','周日']
            }
        ],
        yAxis : [
            {
                type : 'value',
                axisLabel : {
                    formatter : human_size,
                } ,
            }
        ],
        series : [
            //
        ]
    };
    {
        option.xAxis[0].data = [];
        for(var i=%d;i>0;i--){
            option.xAxis[0].data.push(i+'min以前');
        }
    }
    {
        var data = {};
        data['name'] = '总出口';
        data['type'] = 'line';
        data['areaStyle'] = {normal: {shadowBlur: 10}};
        data['stack'] = 'tiled';
        data['smooth'] = true;
        data['data'] = log2['总出口_FF-FF-FF-FF-FF-FF'];
        option.series.push(data);
    }
    delete log2['总出口_FF-FF-FF-FF-FF-FF'];
    {

        for(var mac in log2){
            var data = {};
            data['name'] = human[mac.substring(mac.indexOf('_')+1)];
            data['type'] = 'bar';
            data['stack'] = 'tiled';
            data['data'] = log2[mac];
            data['smooth'] = true;
            option.series.push(data);
        }
    }
    echarts.init(document.getElementById('charts')).setOption(option);
</script>
</html>
''' % (J.dumps(human_map), J.dumps(log2), time.strftime('%H:%M'), content, STEP))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        dst = sys.argv[1]
    else:
        dst = time.strftime('%y%j%H%M')
    main(int(dst))