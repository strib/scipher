#!/usr/bin/env python

import cPickle
import itertools
import string

vowels='AEIOUYaeiouy'

t=["".join(p) for p in itertools.product(string.uppercase, repeat=3) if
   len(filter(lambda y: len(y) >= 1, [filter(lambda x: x in vowels, p)])) > 0]

t.extend(["".join(p) for p in itertools.product(string.uppercase, repeat=4) if
   len(filter(lambda y: len(y) >= 2, [filter(lambda x: x in vowels, p)])) > 0])

t.extend(["".join(p) for p in itertools.product(string.uppercase, repeat=5) if
   len(filter(lambda y: len(y) >= 2, [filter(lambda x: x in vowels, p)])) > 0])

i = 0
d = {}
for w in t:
    print w
    d[w] = i
    i += 1

f = open("cfp_conf_names.pickle", 'wb')
cPickle.dump(d, f)
f.close()
