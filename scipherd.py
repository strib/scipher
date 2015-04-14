#!/usr/bin/env python

# adapted from http://zguide.zeromq.org/py:asyncsrv

import argparse
import cfp_common
import collections
import decode
import encode
import io
import nltk
import os
import pickle
import re
import sys
import tempfile
import threading
import zmq

Task = collections.namedtuple('Task', ['encode', 'infile', 'outfile'])

def tprint(msg):
    """like print, but won't get newlines confused with multiple threads"""
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()

class States:
    def __init__(self):
        self.encode_states = {}
        self.decode_states = {}
        # get the latest version and work backwards
        version = cfp_common.CfpCommon.get_latest_common().version()
        self.latest_version = version
        while version >= 0:
            common = cfp_common.CfpCommon.get_common_for_version(version)
            if common is None:
                continue

            # encode state
            header_grammar = nltk.data.load("file:%s" %
                                            common.header_cfg_filename(),
                                            'cfg')
            body_grammar = nltk.data.load("file:%s" %
                                          common.body_cfg_filename(),
                                          'cfg')
            space_before = re.compile('\s([%s])' %
                                      common.chars_to_remove_a_space_before())
            space_after = re.compile('([%s])\s' %
                                     common.chars_to_remove_a_space_after())
            last_or_nots = common.choose_last_or_nots()
            estate = encode.EncodeState("", None, common, header_grammar,
                                        body_grammar, {}, space_before,
                                        space_after, last_or_nots, None)
            self.encode_states[version] = estate

            # decode state
            de_header_grammar = decode.load_and_norm_grammar(
                common.header_cfg_filename())
            de_body_grammar = decode.load_and_norm_grammar(
                common.body_cfg_filename())
            de_space_before = re.compile(
                '([%s])' % common.chars_to_remove_a_space_before())
            de_space_after = re.compile(
                '([%s])' % common.chars_to_remove_a_space_after())
            destate = decode.DecodeState(common, "", 0, de_header_grammar,
                                         de_body_grammar, {}, de_space_before,
                                         de_space_after, None)
            self.decode_states[version] = destate

            version -= 1

class Worker(threading.Thread):
    """ServerWorker"""
    def __init__(self, context, states):
        threading.Thread.__init__ (self)
        self.context = context
        self.states = states

    def process_encode(self, infile, outfile):
        input_text = ""
        inf = io.open(infile, 'r', encoding='utf-8')
        for line in inf:
            input_text += line
        inf.close()

        s = self.states.encode_states[self.states.latest_version]
        state = encode.EncodeState(input_text, encode.Bitstring(), s.common,
                                   s.header_grammar, s.body_grammar, {},
                                   s.space_before, s.space_after,
                                   s.last_or_nots, encode.LastTime())
        (header, body) = encode.do_encode(state)

        outf = io.open(outfile, 'w', encoding='utf-8')
        outf.write("%s\n\n%s\n" % (header, body))
        outf.close()

    def process_decode(self, infile, outfile):
        inf = io.open(infile, 'r', encoding='utf-8')
        # search until blank line:
        header = ""
        header_lines = []
        for line in inf:
            line = line.rstrip()
            # we hit a blank line, and we have at least one line already
            if not line and len(header_lines) > 0:
                break
            header_lines.append(line)
            header = " ".join(header_lines)

        (conf_name, mask, version, ls_len) = decode.decode_conf_name(header)
        s = self.states.decode_states.get(version, None)
        if s is None:
            inf.close()
            return

        body_text = ""
        for line in inf:
            body_text += line
        inf.close()

        state = decode.DecodeState(s.common, conf_name, mask,
                                   s.header_grammar, s.body_grammar, {},
                                   s.space_before, s.space_after, decode.Done())
        msg = decode.decode(header, body_text, state, ls_len)

        outf = io.open(outfile, 'w', encoding='utf-8')
        outf.write(msg)
        outf.close()

    def run(self):
        worker = self.context.socket(zmq.DEALER)
        worker.connect('inproc://backend')
        tprint('Worker started')
        while True:
            ident, task = worker.recv_multipart()
            task = pickle.loads(task)
            tprint('Worker received %s from %s' % (task, ident))
            ok = True
            try:
                if task.encode:
                    self.process_encode(task.infile, task.outfile)
                else:
                    self.process_decode(task.infile, task.outfile)
                worker.send_multipart([ident, str(True)])
            except Exception as e:
                outf = io.open(task.outfile, 'w', encoding='utf-8')
                outf.write("%s\n" % unicode(e))
                outf.close()
                worker.send_multipart([ident, str(False)])

        worker.close()


def call_daemon(socket_name, encode, infile_arg, outfile_arg):
     infile = infile_arg
     if not infile:
          # write the data to a temporary file and call the daemon
          (inf, infile) = tempfile.mkstemp()
          for line in sys.stdin:
               os.write(inf, line)
          os.close(inf)

     outfile = outfile_arg
     if not outfile:
          (outf, outfile) = tempfile.mkstemp()
          os.close(outf)
     task = Task(encode, infile, outfile)

     context = zmq.Context()
     socket = context.socket(zmq.DEALER)
     identity = u'worker-%s' % infile
     socket.identity = identity.encode('ascii')
     socket.connect(socket_name)
     socket.send_pyobj(task)
     ok = socket.recv() == "True"

     if not outfile_arg:
          outf = open(outfile, 'r')
          for line in outf:
               if ok:
                   print line,
               else:
                   sys.stderr.write(line)
          outf.close()
          os.unlink(outfile)

     if not infile_arg:
          os.unlink(infile)
     return ok

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', metavar='S', type=str,
                        default="ipc:///tmp/scipherd",
                        help='the local socket to bind to')
    parser.add_argument('--workers', metavar='w', type=int, default=1,
                        help='the local socket to bind to')
    args = parser.parse_args()
    states = States()

    context = zmq.Context()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind(args.socket)

    backend = context.socket(zmq.DEALER)
    backend.bind('inproc://backend')

    workers = []
    for i in range(args.workers):
        worker = Worker(context, states)
        worker.start()
        workers.append(worker)

    poll = zmq.Poller()
    poll.register(frontend, zmq.POLLIN)
    poll.register(backend,  zmq.POLLIN)

    # load all grammars

    while True:
        sockets = dict(poll.poll())
        if frontend in sockets:
            ident, msg = frontend.recv_multipart()
            tprint('Server received a message from id %s' % ident)
            backend.send_multipart([ident, msg])
        if backend in sockets:
            ident, msg = backend.recv_multipart()
            tprint('Sending a message to frontend id %s' % ident)
            frontend.send_multipart([ident, msg])

    frontend.close()
    backend.close()
    context.term()

if __name__ == "__main__":
     main()
