#!/usr/bin/env python

import argparse
import cfp_common
import collections
import math
import nltk
import re
import scipherd
import sys
import time

DecodeState = collections.namedtuple('DecodeState',
                                     ['common', 'conf_name', 'mask',
                                      'header_grammar', 'body_grammar',
                                      'list_bits', 'space_before',
                                      'space_after', 'done'])

# To find the code, we have to binary search the conf name file.  There are
# 2097152 possible names.  Binary search cribbed from
# http://interactivepython.org/courselib/static/pythonds/SortSearch/TheBinarySearch.html
def binsearch_conf_names(conf_name):
     first = 0
     last = 2097152

     f = open(cfp_common.CfpCommon.conf_names_filename(), 'r')
     while first <= last:
          midpoint = (first + last)//2
          mid_name = cfp_common.CfpCommon.conf_name_from_index(f, midpoint)
          if mid_name == conf_name:
               return midpoint

          if ((len(conf_name) < len(mid_name)) or
              (len(conf_name) == len(mid_name) and conf_name < mid_name)):
               last = midpoint - 1
          else:
               first = midpoint + 1
     f.close()

class Done():
     def __init__(self):
          self.reset(0)

     def reset(self, length):
          self.done = False
          self.bits_left = length
          self.total_len = length

def get_number(tree, grammar, state, in_list_arg = None):
    if type(tree) != nltk.Tree:
         return ((tree,), [])
    nt_label = nltk.Nonterminal(tree.label())
    if state.done.done:
         return ((nt_label,), [])

    prods = grammar.productions(nt_label)
    rhs = ()
    num = []

    # come up with a format with the right number of leading zeroes
    bits = 0
    if len(prods) >= 3:
         bits = int(math.log(len(prods)-1, 2))
    formatstr = "{0:0%db}" % bits
    prevPow2 = math.pow(2, bits)

    in_list = in_list_arg
    if not in_list and nt_label in state.list_bits:
         in_list = nt_label

    use_bits = True
    if nt_label in state.common.choose_last_or_nots():
         use_bits = False

    # Consume list bits before we start recursing, since that's the order
    # ./encode.py does it.
    is_list = False
    if bits > 0 and in_list in state.list_bits:
         is_list = True
         if use_bits:
              # if we know that this is going to be the end of a list such
              # that the power of 2 was chosen, then don't bother subtracting
              # the bits from the main done.
              if (nt_label in state.common.list_recursive_terms() and
                  state.list_bits[in_list] <= 0 and len(state.list_bits) > 1):
                   use_bits = False

              state.list_bits[in_list] -= bits
              #print ("Consumed %d bits for list %s, %s left" %
              #       (bits, in_list, list_bits[in_list]))

    prev_bits_left = state.done.bits_left
    if use_bits:
         #print "(%s) Consumed %s bits for %s" % (prev_bits_left, bits, nt_label)
         state.done.bits_left -= bits

    # set up list_bits if needed, before recursing:
    subtrees = tree.subtrees().next()
    if len(state.list_bits) == 0 and nt_label == nltk.Nonterminal("CFP_BODY"):
         body_rhs = tuple(nltk.Nonterminal(t.label()) for t in subtrees)
         for p in prods:
              if p.rhs() == body_rhs:
                   state.list_bits.update(
                        state.common.calc_list_bits(state.done.total_len, p))
                   break

    child_bits = 0
    for t in subtrees:
        (t_rhs, t_num) = get_number(t, grammar, state, in_list)
        rhs += t_rhs
        num.extend(t_num)

    end_list = False
    if bits == 0:
         # If this had fewer than 3 rules, the first one was always
         # used, so don't produce any bits
         return ((nt_label,), num)
    elif is_list:
         if (in_list not in state.list_bits or
             (state.list_bits[in_list] <= 0 and len(state.list_bits) > 1)):
              end_list = True

    for i in range(len(prods)):
        if prods[i].rhs() == rhs:
            if (len(state.list_bits) == 0 and
                nt_label == nltk.Nonterminal("CFP_BODY")):
                 state.list_bits.update(state.common.calc_list_bits(
                      state.done.total_len, prods[i]))

            if prev_bits_left <= 0:
                state.done.done = True
                return ((nt_label,), [])
            elif is_list and i == prevPow2:
                 if use_bits:
                      state.done.bits_left += bits  # encode didn't count these
                 if in_list in state.list_bits:
                      bits_left = state.list_bits[in_list]
                      if bits_left <= 0 and len(state.list_bits) > 1:
                           del state.list_bits[in_list]
                 # end of the list -- still count the choices below us
                 return ((nt_label,), num)
            else:
                 istring = formatstr.format(i)
                 #print ("(%s) Using %s bits %s (%s -> %s)" %
                 #       (prev_bits_left, bits, istring, nt_label, rhs))
                 return ((nt_label,), [istring]+num)
    print "Couldn't find rhs for label %s, rhs %s" % (rhs, tree.label())

def bin_to_text(binstring, mask):
    return ''.join(unichr(int(binstring[i:i+8], 2)^mask)
                   for i in xrange(0, len(binstring), 8))

quote_re = re.compile("\"([^\"]*)\"")
def tolower_inquotes(matchobj):
     return "\"%s\"" % matchobj.group(1).lower()

def load_and_norm_grammar(grammar_file):
     gs = open(grammar_file).read().decode("UTF-8")
     # when decoding, treat all terminals as lower case
     norm_gs = quote_re.sub(tolower_inquotes, gs)
     return nltk.CFG.fromstring(norm_gs)

def parse_text(text, grammar, state, length):
     parser = nltk.parse.LeftCornerChartParser(grammar)
     # add in a marker for single-line spaces, otherwise they will get split out
     if isinstance(text, str):
          text = text.decode("utf-8")
     words = text.lower().replace("\n\n", "\nNEWLINE_SPACE\n").split()
     ready_words = [w.replace("NEWLINE_SPACE", " ") for w in words]
     parsed = parser.parse(ready_words)

     found = False
     for t in parsed:
          #print t
          if found:
               print "Ambiguous grammar!"
               sys.exit(-1)

          found = True
          state.done.reset(length)
          (l, n) = get_number(t, grammar, state)
          if len(n) < 1:
               print "Could not decode this text"
               sys.exit(-1)

          # the total length should be "length".  If not, cut off
          # some bits from the last number
          bitlength = sum(len(s) for s in n)
          over = bitlength - length
          n[-1] = n[-1][over:]
          return "".join(n)

# Reverse pretty print:
#  1) add one space before all punctuation (except '(')
#  2) add one space after '('
# We don't worry about the capitalization because we're going to treat
# everything as lower-case.
def reverse_pretty_print(line, state):
     ppline = state.space_before.sub(r' \1', line)
     ppline = state.space_after.sub(r'\1 ', ppline)
     return ppline

def reverse_pretty_print_all(text, state):
     return "\n".join([reverse_pretty_print(line, state)
                       for line in text.splitlines()])

def decode_conf_name(header):
     # Extract data from the header.  First find and translate
     # the conference name.  We must do this manually, since we can't rely
     # on the grammar yet (don't know what version was used to encode).
     # Look for the first location that has 3-5 capital letters that are
     # not 'CFP'.
     groups = re.findall("\s[A-Z]{3,5}\s", header)
     conf_name = ""
     for g in groups:
          c = g.lstrip().rstrip()
          if c != "CFP":
               conf_name = c
               break

     if not conf_name:
          raise Exception("Bad header format -- could not find conference name")

     index = binsearch_conf_names(conf_name)
     mask = index >> 13
     version = ((index >> 5) & 0xff) ^ mask
     ls_len = (index & 0x1f)
     return (conf_name, mask, version, ls_len)

def decode(header, body_text, state, ls_len):
     header = reverse_pretty_print_all(header, state)

     header_binstring = parse_text(header.replace(state.conf_name,
                                                  "CFP_CONF_ABBREV"),
                                   state.header_grammar, state, 15)
     #sys.stderr.write("header: %s\n" % header_binstring)
     ms_len = (int(header_binstring, 2) ^ (state.mask |
                                           (state.mask & 0x7f) << 8))
     body_len = (ms_len << 5) | ls_len

     # replace any links with WEBSITE_LINK (don't replace the punctuation
     # after it, though)
     body_text = re.sub('(http://[\w\.]+\w)(\.?\s)', r'WEBSITE_LINK\2',
                        body_text)
     body_text = re.sub('(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}', r'SUBSTITUTE_DATE', body_text)
     unpretty_text = reverse_pretty_print_all(
          body_text.replace(state.conf_name, "CFP_CONF_ABBREV"), state)

     body_binstring = parse_text(unpretty_text, state.body_grammar, state,
                                 body_len*8)
     if body_binstring is None:
          raise Exception("Couldn't parse the message!")
     return bin_to_text(body_binstring, state.mask)

def main():
     parser = argparse.ArgumentParser()
     parser.add_argument('--socket', metavar='SOCKET', type=str,
                         help='the local socket to bind to')
     parser.add_argument('--infile', metavar='FILE', type=str,
                         help='read from this file instead of stdin')
     parser.add_argument('--outfile', metavar='FILE', type=str,
                         help='write to this file instead of stdout')
     args = parser.parse_args()

     if args.socket:
          ok = scipherd.call_daemon(args.socket, False,
                                    args.infile, args.outfile)
          if ok:
               sys.exit(0)
          else:
               sys.exit(-1)

     # search until blank line:
     header = ""
     header_lines = []
     for line in sys.stdin:
          line = line.rstrip()
          # we hit a blank line, and we have at least one line already
          if not line and len(header_lines) > 0:
               break
          header_lines.append(line)
          header = " ".join(header_lines)

     (conf_name, mask, version, ls_len) = decode_conf_name(header)
     common = cfp_common.CfpCommon.get_common_for_version(version)
     if common is None:
          sys.stderr.write("Unrecognized version: %s\n" % version)
          sys.exit(-1)

     body_text = ""
     for line in sys.stdin:
          body_text += line

     header_grammar = load_and_norm_grammar(common.header_cfg_filename())
     body_grammar = load_and_norm_grammar(common.body_cfg_filename())
     space_before = re.compile('([%s])' %
                               common.chars_to_remove_a_space_before())
     space_after = re.compile('([%s])' % common.chars_to_remove_a_space_after())
     state = DecodeState(common, conf_name, mask, header_grammar, body_grammar,
                         {}, space_before, space_after, Done())

     print decode(header, body_text, state, ls_len),

if __name__ == "__main__":
     main()
