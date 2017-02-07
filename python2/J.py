#!/usr/bin/env python
# -*- coding:utf-8 -*-
import json
import traceback

import sys

buff = ""
try:
    while True:
        buff += raw_input()
except EOFError as e:
    pass
except Exception as e:
    traceback.print_exc()
if len(buff) == 0:
    pass
else:
    try:
        obj = json.loads(buff)
        if len(sys.argv) >= 2:
            for key in sys.argv[1:]:
                if key in obj:
                    obj = obj[key]
        print(json.dumps(obj, indent=1))
    except Exception as e:
        traceback.print_exc()
        print buff
