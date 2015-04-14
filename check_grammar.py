#!/usr/bin/env python

from itertools import groupby
import math
import nltk
import sys

def do_check(filename):
    body_grammar = nltk.data.load("file:%s" % filename, 'cfg')
    uses = {}
    print "Nonterminals with no productions:"
    for label,prods in groupby(body_grammar.productions(),
                               lambda p: p.lhs().symbol()):
        l = label
        if l not in uses:
            uses[l] = 0
        np = 0
        for p in prods:
            np += 1
            for term in p.rhs():
                s = repr(term)
                if s not in uses:
                    uses[s] = 0
                uses[s] += 1
                if (not isinstance(term, basestring) and
                    len(body_grammar.productions(term)) == 0):
                    print "* %s (label %s)" % (term, label)
        # check # of productions
        #if np >= 3:
        #    bits = math.log(np-1, 2)
        #    if int(bits) != bits:
        #        print "*** label %s has %s productions" % (label, np)


    print "Nonterminals with duplicate productions:"
    for label,prods in groupby(body_grammar.productions(),
                               lambda p: p.lhs().symbol()):
        l = label
        pset = set()
        #done = set()
        for p in prods:
            if p in pset:# and p not in done:
                print "* term %s: %s" % (label, p)
                #done.add(p)
            pset.add(p)
            for term in p.rhs():
                s = repr(term)
                if s not in uses:
                    uses[s] = 0
                uses[s] += 1
                if (not isinstance(term, basestring) and
                    len(body_grammar.productions(term)) == 0):
                    print "* %s (label %s)" % (term, label)


    print "\nNonterminals with no uses:"
    print "grep -v ",
    for t,u in uses.iteritems():
        if u == 0 and t != "START":
            print "-e \"^%s -\" " % t,
    print filename

do_check(sys.argv[1])
