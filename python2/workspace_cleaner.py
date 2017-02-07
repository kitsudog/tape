#!/usr/bin/env python
# -*- coding:utf-8 -*-
from __future__ import print_function

import glob
import os
import re
import shutil
import subprocess
import sys
import traceback
from optparse import OptionParser

LEVEL_SOURCE = 99  # 仅保留代码
LEVEL_PROJECT = 10  # 保留项目配置与设置相关


def human_size(s):
    s = int(s)
    if s > 1024 * 1024 * 1024 * 1024:
        return "%.3fT" % (s * 1.0 / (1024 * 1024 * 1024 * 1024))
    elif s > 1024 * 1024 * 1024:
        return "%.3fG" % (s * 1.0 / (1024 * 1024 * 1024))
    elif s > 1024 * 1024:
        return "%.3fM" % (s * 1.0 / (1024 * 1024))
    elif s > 1024:
        return "%.3fK" % (s * 1.0 / 1024)
    else:
        return "%dB" % s


class FailError(Exception):
    def __init__(self, msg, args=None):
        if args is not None:
            msg = msg % args
        Exception.__init__(self, msg)


class Files:
    def __init__(self, title, base):
        self.title = title
        self.deletes = []
        self.delete_file_set = set()
        self.base = base

    def d(self, dir_path):
        for path in glob.glob(os.path.join(self.base, dir_path)):
            path = os.path.realpath(path)
            if path in self.delete_file_set:
                # 已经添加过了
                return
            self.deletes.append((self.title, path))
            self.delete_file_set.add(path)

    def extends(self, files):
        for title, d in files.deletes:
            if d in self.delete_file_set:
                # 已经添加过了
                continue
            self.deletes.append((title, d))
            self.delete_file_set.add(d)

    def all(self):
        ret = []
        for title, d in self.deletes:
            tmp = glob.glob(d)
            # 筛选无意义的项
            ret.extend(map(lambda x: (title, x), tmp))
        return ret


def debug(msg, args=None):
    if args is not None:
        msg = msg % args
    print('[DEBUG] ' + msg)


def error(msg, args=None):
    if args is not None:
        msg = msg % args
    print('[ERROR] ' + msg)


def fatal(msg, args=None):
    if args is not None:
        msg = msg % args
    print('[FATAL] ' + msg)
    sys.exit(1)


def info(msg, args=None):
    if args is not None:
        msg = msg % args
    print('[INFO_] ' + msg)


def try_run(func, exit_when_fail=True, verbos=True):
    def wrapper(*args, **kwargs):
        log = fatal if exit_when_fail else error
        try:
            return func(*args, **kwargs)
        except FailError as e:
            if verbos:
                log(e.message)
        except OSError as e:
            log('[%d] %s' % (e.errno, e.strerror))
            traceback.print_exc()
        except Exception as e:
            if e.message is None or len(e.message) == 0:
                log('出现错误')
            else:
                log(e.message)
            traceback.print_exc()
            pass
        if exit_when_fail:
            exit(1)

    return wrapper


def _exists(path1, path2=None):
    if path2 is None:
        path = path1
    else:
        path = os.path.join(path1, path2)
    if not os.path.exists(path):
        raise FailError("文件[%s]不存在", path)


def _exists_dir(path1, path2=None):
    if path2 is None:
        path = path1
    else:
        path = os.path.join(path1, path2)
    if not os.path.exists(path):
        raise FailError("文件[%s]不存在", path)
    if not os.path.isdir(path):
        raise FailError("目标[%s]不是文件夹", path)


def _remove(path1, path2=None):
    if path2 is None:
        path = path1
    else:
        path = os.path.join(path1, path2)
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)


def _remove_dir(path1, path2=None):
    if path2 is None:
        path = path1
    else:
        path = os.path.join(path1, path2)
    if not os.path.isdir(path):
        return
    if os.path.islink(path):
        return
    shutil.rmtree(path)


def run_cmd(cmd, pwd):
    p = subprocess.Popen(cmd, cwd=pwd, shell=True, stdout=subprocess.PIPE)
    ret = ""
    while p.poll() is None:
        ret += p.stdout.read()
    return ret


def _clean_git(ws_path, ignores=None):
    # TODO: 向上追溯git
    _exists_dir(ws_path, '.git')
    # 执行
    files = Files('git', ws_path)
    content = run_cmd('git clean -dX -n', pwd=ws_path)
    for f in re.compile('Would remove (.+)').findall(content):
        files.d(f)
    return files


def _clean_svn(ws_path, ignores=None):
    pass


def clean_vcs(ws_path, ignores=None):
    files = Files('vcs', '.')
    for func in [_clean_git, _clean_svn]:
        ret = try_run(func, exit_when_fail=False, verbos=False)(ws_path, ignores=ignores)
        if isinstance(ret, Files):
            files.extends(ret)
    return files


def clean_ios(ws_path, level=LEVEL_SOURCE):
    xcodeprojs = glob.glob(os.path.join(ws_path, '*.xcodeproj'))
    if len(xcodeprojs) == 0:
        raise FailError('目录[%s]不是ios项目', ws_path)
    files = Files('iOS', ws_path)
    vcs = clean_vcs(ws_path)
    for xcodeproj in xcodeprojs:
        if level >= LEVEL_PROJECT:
            files.d(os.path.join(xcodeproj, 'xcuserdata'))  # compile
            files.d(os.path.join(xcodeproj, 'project.xcworkspace'))  # compile
            # TODO: 系统中的相关文件
        if level >= LEVEL_SOURCE:
            files.extends(vcs)
    # todo: ~/Library/Developer/Xcode/DerivedData
    return files


def clean_android(ws_path, level=LEVEL_SOURCE):
    # 检测类型
    _exists(ws_path, 'project.properties')
    _exists(ws_path, 'AndroidManifest.xml')
    _exists_dir(ws_path, 'src')
    _exists_dir(ws_path, 'res')

    # 开始处理
    vcs = clean_vcs(ws_path)
    files = Files('Android', ws_path)
    if level >= LEVEL_PROJECT:
        files.d('obj')  # ndk
        files.d('bin')  # compile
        files.d('gen')  # compile
    if level >= LEVEL_SOURCE:
        files.extends(vcs)
    return files


def clean_cocos2dx(ws_path, level=LEVEL_SOURCE):
    # 检测类型
    _exists(ws_path, 'cocos2d')
    _exists_dir(ws_path, 'Classes')
    _exists_dir(ws_path, 'Resources')

    # 开始处理
    vcs = clean_vcs(ws_path)
    files = Files('Cocos2dx', ws_path)
    if level >= LEVEL_PROJECT:
        files.d('bin')
        # android
        files.extends(clean_android(os.path.join(ws_path, 'proj.android')))
        files.extends(clean_android(os.path.join(ws_path, 'cocos2d', 'cocos', 'platform', 'android', 'java')))
        files.d(os.path.join('proj.android', 'assets'))
        # iOS
        files.extends(clean_ios(os.path.join(ws_path, 'proj.ios_mac')))
        files.extends(clean_ios(os.path.join(ws_path, 'cocos2d', 'build')))
        pass
    if level >= LEVEL_SOURCE:
        # android
        files.d(os.path.join('proj.android', 'lib', 'armeabi', 'libcocos2dcpp.so'))
        # todo: 匹配默认生成的文件并删除
        files.extends(vcs)
    return files


def clean_unity3d(ws_path, level=LEVEL_SOURCE):
    # 检测类型
    _exists_dir(ws_path, 'Assets')
    _exists_dir(ws_path, 'ProjectSettings')
    # 开始处理
    vcs = clean_vcs(ws_path)
    files = Files('Unity3D', ws_path)
    if level >= LEVEL_PROJECT:
        # todo识别生成的库
        pass
    if level >= LEVEL_SOURCE:
        files.extends(vcs)
        # Unity3D 生成的
        files.d('Library')
        files.d('Temp')
        files.d('obj')
        # MonoDevelop 生成的
        files.d('*.csproj')
        files.d('*.sln')
        files.d('*.userprefs')
    return files


def clean_python(ws_path, level=LEVEL_SOURCE):
    _exists(ws_path, '__init__.py')
    files = Files('python', ws_path)
    if level >= LEVEL_PROJECT:
        # todo识别生成的库
        files.d('*.pyc')
        pass
    if level >= LEVEL_SOURCE:
        pass
    return files


def list_all(path):
    ret = []
    for f in os.listdir(path):
        f = os.path.join(path, f)
        ret.append(f)
    return ret


def list_dir(path, remove_dir_set, base, out_links):
    ret = set()
    for f in os.listdir(path):
        f = os.path.join(path, f)
        if os.path.isdir(f):
            # 针对符号链接要排除处理过的
            real = os.path.realpath(f)
            if out_links or real.startswith(base):
                ret.add(real)
            else:
                # 外部的
                info("Pass [%s]=>[%s]" % (format_path(f, base), real))
                continue
    ret -= remove_dir_set
    remove_dir_set.update(ret)
    return sorted(ret)


def size(file_or_dir):
    if os.path.isfile(file_or_dir):
        return os.path.getsize(file_or_dir)
    if os.path.isdir(file_or_dir):
        return sum(map(size, list_all(file_or_dir)))
    return 0


def format_path(path, base=None):
    path = os.path.abspath(path)
    if base is not None:
        if path.find(base) == 0:
            path = '.' + path[len(base):]
        else:
            # 部分情况下显示相对路径
            pass
    return path


def remove(files, dry_run=False, base=None, remove_dir_set=set()):
    total = 0

    def mark_dir(_):
        if os.path.islink(_):
            info(_)
            remove_dir_set.add(_)

    if dry_run:
        for t, f_path in files.all():
            mark_dir(f_path)
            tmp = size(f_path)
            if base is not None:
                f = format_path(f_path, base)
            if os.path.isfile(f_path):
                info("%s => %s [%s]" % (t, f, human_size(tmp)))
            else:
                info("%s => %s%s* [%s]" % (t, f, os.path.sep, human_size(tmp)))
            total += tmp
    else:
        for t, f in files.all():
            mark_dir(f)
            total += size(f)
            if os.path.isfile(f) or os.path.islink(f):
                _remove(f)
            elif os.path.isdir(f):
                _remove_dir(f)
    return total


def cleaner(ws_path, level=LEVEL_SOURCE, dry_run=False, out_links=False):
    """

    :param dry_run:
    :param level:
    :param ws_path: 目标目录
    :param out_links: 清理外链
    :return:
    """
    if not os.path.isdir(ws_path):
        fatal("[%s] is not directory", ws_path)

    dirs = [ws_path]
    total = 0
    remove_dir_set = set()
    while len(dirs):
        d = dirs.pop()
        cnt = 0
        for func in [clean_unity3d, clean_cocos2dx, clean_android, clean_ios, clean_python]:
            ret = try_run(func, exit_when_fail=False, verbos=False)(d, level)
            # TODO: 智能的排除已经处理的目录
            # 单一清理
            if ret is None:
                continue
            else:
                cnt += 1
                total += remove(ret, dry_run=dry_run, base=ws_path, remove_dir_set=remove_dir_set)
        if cnt == 0:
            # 当前目录没有匹配的规则
            dirs.extend(list_dir(d, remove_dir_set, base=ws_path, out_links=out_links))
    info('Total[%s]', human_size(total))


def main(argv=None):
    if argv is None:
        argv = sys.argv
    parser = OptionParser("Usage: %prog [options] <path>")
    parser.add_option("-d", "--dry", action="store_true", dest="dry", help="no remove just list", default=False)
    parser.add_option("-O", "--out-links", action="store_true", dest="out_links", help="allow links out of workspace",
                      default=False)
    parser.add_option("-S", "--source-only", action="store_true", dest="source_only", help="keep source only",
                      default=False)
    (options, args) = parser.parse_args(argv)
    if len(args) < 2:
        parser.print_help()
    else:
        ws_path = args[1]
        if str(ws_path).endswith(os.path.sep):
            ws_path = str(ws_path)[:-len(os.path.sep)]
        if not os.path.exists(ws_path):
            sys.stderr.write('path [%s] not exists\n' % ws_path)
            exit(1)
        if not os.path.isdir(ws_path):
            sys.stderr.write('path [%s] not dir\n' % ws_path)
            exit(1)
        if os.path.islink(ws_path):
            ws_path = os.path.realpath(ws_path)
        cleaner(ws_path=ws_path,
                level=LEVEL_SOURCE if options.source_only else LEVEL_PROJECT,
                dry_run=options.dry,
                out_links=options.out_links
                )


if __name__ == '__main__':
    main(sys.argv)
