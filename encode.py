#!/usr/bin/env python

import argparse
import cfp_common
import collections
import datetime
import math
import nltk
import re
import Queue
import random
import scipherd
import sys
import time
import zmq

####
# from http://bytes.com/topic/python/answers/828486-ascii-binary-conversion
def a2b(a, mask):
     ord_a = ord(a)
     if ord_a >= 256:
          raise Exception("Unsupported character: %s" % a)
     ai = ord_a ^ mask
     return ''.join('01'[(ai >> x) & 1] for x in xrange(7, -1, -1))
####

class Bitstring:
     def __init__(self):
          self.reset("")

     def reset(self, bitstring):
          self.bitstring = bitstring
          self.index = 0

class LastTime:
     def __init__(self):
          self.last_time = time.time()

     def next_time(self):
          self.last_time += random.randint(7, 60)*(24*60*60)
          return self.last_time

EncodeState = collections.namedtuple('EncodeState',
                                     ['input_text', 'bitstring', 'common',
                                      'header_grammar', 'body_grammar',
                                      'list_bits', 'space_before',
                                      'space_after', 'last_or_nots',
                                      'last_time'])

def choose(nonterm, in_list, prods, state):
     if nonterm in state.last_or_nots:
          # if True, use the last one, otherwise, use anything but.
          # this choice uses no bits
          if state.last_or_nots[nonterm]:
               return prods[len(prods)-1]
          else:
               return random.choice(prods[:-1])
     elif state.bitstring.index >= len(state.bitstring.bitstring):
          # We're past the end of the message, so just pick randomly
          return random.choice(prods)
     elif len(prods) < 3:
          return prods[0]

     bits = int(math.log(len(prods)-1, 2))
     prevPow2 = math.pow(2, bits)

     # For lists, only pick the end of the list once we've used all
     # the bits, or we're out of bits.  Unless we're the last list
     # left, then keep going until we consume all bits
     end_list = False
     if in_list and in_list in state.list_bits:
          bits_left = state.list_bits[in_list]
          if (bits_left <= 0 and len(state.list_bits) > 1 and
              nonterm in state.common.list_recursive_terms()):
               end_list = True
               del state.list_bits[in_list]
          else:
               state.list_bits[in_list] = bits_left - bits
               #print ("Consuming %s bits for list %s (%s left)" %
               #       (bits, in_list, state.list_bits[in_list]))

     # otherwise, use the first 'bits' bits to pick the index
     index = int(prevPow2)
     if not end_list:
          strindex = state.bitstring.bitstring[state.bitstring.index:bits+
                                               state.bitstring.index]
          index = int(strindex, 2)
          #print ("(%s) Using bits %s (%s -> %s)" %
          #       (len(state.bitstring.bitstring)-state.bitstring.index, strindex, nonterm, prods[index]))
          state.bitstring.index += bits
          state.bitstring.index = min(state.bitstring.index,
                                      len(state.bitstring.bitstring))
     # now interpret as an int
     prod = prods[index]
     if len(state.list_bits) == 0 and nonterm == nltk.Nonterminal("CFP_BODY"):
          # set the list bits
          state.list_bits.update(
               state.common.calc_list_bits(len(state.input_text)*8, prod))
     return prod

def expand(grammar, nonterm, state, in_list = None):
     # pick random production, recurse
     prods = grammar.productions(nonterm)
     if len(prods) == 0:
          return prods
     p = choose(nonterm, in_list, prods, state)
     return p.rhs()

def expand_all(grammar, nonterm, state):
     result = ""
     queue = Queue.LifoQueue()
     queue.put_nowait(nonterm)
     # do this iteratively; recursively blows past python's recursive limit
     in_list = None
     len_at_start_of_list = 0
     while not queue.empty():
          head = queue.get_nowait()
          # Keep track of being in a list until all the bits for the list
          # have been used up
          if head in state.list_bits:
               in_list = head
               len_at_start_of_list = queue.qsize()
          # done with the list once we consume the next item in the queue
          if in_list and queue.qsize() < len_at_start_of_list:
               in_list = None
          terms = expand(grammar, head, state, in_list)
          if len(terms) == 0:
               if isinstance(head, basestring):
                    result = " ".join([result, head])
               else:
                    result = " ".join([result, str(head)])
          else :
               # put them into the lifo queue backwards, so we'll get the
               # first one out
               for nt in reversed(terms):
                    if nt in state.common.append_newlines():
                         queue.put_nowait(nltk.Nonterminal("\n"))
                    queue.put_nowait(nt)
     return result

# Must be determinstically reversible by the decoder, so use the
# following rules:
#  1) Erase spaces at the beginning and end of every line
#  2) If the first letter of the line is not capitalized, make it so
#  3) remove one space before all punctuation (except '(')
#  4) remove one space after '('
def pretty_print(line, state):
     ppline = line.lstrip().rstrip()
     if len(ppline) > 0 and ppline[0].islower():
          ppline = ppline[0].upper() + ppline[1:]
     ppline = state.space_before.sub(r'\1', ppline)
     ppline = state.space_after.sub(r'\1', ppline)
     return ppline

def pretty_print_all(text, state):
     return "\n".join([pretty_print(line, state) for line in text.splitlines()])

# first thing: determine the header (subject line):
#
#  The conference name is 3-5 upper-case characters.  For 3 letters,
#  at least one must be a vowel; for 4-5 letters, at least 2 must be.
#  This allows for roughly 2.5M conference names, or 21 bits to work
#  with.
#
#  bits 0-7: a random XOR mask for the body of the data
#  bits 8-15: a version number for the grammar itself (masked)
#  bits 16-20: the least significant 5 bits of the input text
#
#  Once this is figured out, generate the header by using a masked
#  bitstring out of the rest of the byte-length of the input text
#  (15 bytes, capping the whole thing at 1M)

def do_encode(state, website = None):
     mask = random.randint(0,255)
     version = state.common.version()
     if version < 0 or version > 255:
          print "Bad grammar version: %d" % version
          sys.exit(-1)

     ls_len = len(state.input_text) & 0x1f

     name_index = (mask << 13) | ((version ^ mask) << 5) | ls_len
     f = open(cfp_common.CfpCommon.conf_names_filename(), 'r')
     conf_name = cfp_common.CfpCommon.conf_name_from_index(f, name_index)
     f.close()
     #print "3) %s" % time.time()

     ms_len = len(state.input_text) >> 5
     masked_len = "{0:015b}".format(ms_len ^ (mask | (mask & 0x7f) << 8))
     #sys.stderr.write("header: %s\n" % masked_len)
     state.bitstring.reset(masked_len)
     header = expand_all(state.header_grammar,
                         state.header_grammar.start(), state)
     header = pretty_print_all(header.replace("CFP_CONF_ABBREV", conf_name),
                               state)

     #print "4) %s" % time.time()

     body_string = "".join([a2b(c, mask) for c in state.input_text])
     state.bitstring.reset(body_string)
     body = expand_all(state.body_grammar, state.body_grammar.start(), state)
     if website:
          body = body.replace("WEBSITE_LINK", website)

     #print "5) %s" % time.time()

     # Replace dates:
     date_re = re.compile("(SUBSTITUTE_DATE)")
     def sub_datetime(matchobj):
          # pick a time about one month away from the last one
          next_time = state.last_time.next_time()
          return (datetime.date.fromtimestamp(next_time).strftime("%B %d, %Y").
                  lstrip("0").replace(" 0", " "))
     body = date_re.sub(sub_datetime, body)

     #print "6) %s" % time.time()
     body =  pretty_print_all(body.replace("CFP_CONF_ABBREV", conf_name), state)
     return (header, body)

def main():
     parser = argparse.ArgumentParser()
     parser.add_argument('--seed', metavar='S', type=int,
                         help='the random number generator seed')
     parser.add_argument('--socket', metavar='SOCKET', type=str,
                         help='the local socket to bind to')
     parser.add_argument('--infile', metavar='FILE', type=str,
                         help='read from this file instead of stdin')
     parser.add_argument('--outfile', metavar='FILE', type=str,
                         help='write to this file instead of stdout')
     parser.add_argument('--website', metavar='W', type=str,
                         help='a website link to include, if any '
                         '(must start with "http://")')
     args = parser.parse_args()

     if args.socket:
          ok = scipherd.call_daemon(args.socket, True,
                                    args.infile, args.outfile)
          if ok:
               sys.exit(0)
          else:
               sys.exit(-1)

     if args.seed:
          seed = args.seed
     else:
          seed = random.randint(0, 2**32)
     random.seed(seed)
     sys.stderr.write("Random seed: %d\n" % seed)

     input_text = ""
     for line in sys.stdin:
          input_text += line.decode('utf-8')

     if len(input_text) > 2**20:
          print "Input text must be smaller than 1MB."
          sys.exit(-1)

     common = cfp_common.CfpCommon.get_latest_common()
     space_before = re.compile('\s([%s])' %
                               common.chars_to_remove_a_space_before())
     space_after = re.compile('([%s])\s' %
                              common.chars_to_remove_a_space_after())

     last_or_nots = common.choose_last_or_nots()
     if args.website:
          if args.website.find("http://") != 0:
               sys.stderr.write("Bad website: %s\n" % args.website)
               sys.exit(-1)
          last_or_nots[nltk.Nonterminal("SUBMIT_CLOSING")] = True

     # load grammars
     #print "1) %s" % time.time()
     header_grammar = nltk.data.load("file:%s" % common.header_cfg_filename(),
                                     'cfg')
     body_grammar = nltk.data.load("file:%s" % common.body_cfg_filename(),
                                   'cfg')
     #print "2) %s" % time.time()
     state = EncodeState(input_text, Bitstring(), common, header_grammar,
                         body_grammar, {}, space_before, space_after,
                         last_or_nots, LastTime())
     (header, body) = do_encode(state, args.website)
     print header
     print ""
     print body


if __name__ == "__main__":
     main()
